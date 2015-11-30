
import os
import itertools

if 'TEA_PATH' not in os.environ:
    exit("please defined TEA_PATH, the path of the direct path of the code folder")

import sys
import re

sys.path.insert(0, os.path.join(os.environ['TEA_PATH'], "code/features"))

from Note import Note

from utilities.timeml_utilities import get_text
from utilities.timeml_utilities import get_tagged_entities
from utilities.timeml_utilities import get_text_element
from utilities.timeml_utilities import get_tlinks
from utilities.timeml_utilities import get_make_instances
from utilities.timeml_utilities import get_doctime_timex

from utilities.xml_utilities import get_raw_text
from utilities.pre_processing import pre_processing

from Features import Features

import copy

class TimeNote(Note, Features):

    def __init__(self, timeml_note_path, annotated_timeml_path=None, verbose=False):

        if verbose: print "called TimeNote constructor"

        _Note = Note.__init__(self, timeml_note_path, annotated_timeml_path)
        _Features = Features.__init__(self)

        self._pre_process(timeml_note_path)

        if self.annotated_note_path is not None:

            self.get_tlinked_entities()

        else:
            self.tlinks = None

    def _pre_process(self, timeml_note_path):

        # callls newsreader pipeline, tokenizes, get_features
        data = get_text(timeml_note_path)

        # original text body of timeml doc
        self.original_text = data

        # sent text to newsreader for processing
        tokenized_text = pre_processing.pre_process(data)

        # contains a lot of extra information generated by newsreader, not plain tokens
        self.pre_processed_text = tokenized_text

        # remove all the junk and just get list of list of tokens
        #self.extract_tokenized_text


    def get_timex_iob_labels(self):
        return self.filter_iob_by_type('TIMEX3')

    def get_event_iob_labels(self):
        return self.filter_iob_by_type('EVENT')

    def filter_iob_by_type(self, entity_type):
        assert entity_type in ['EVENT', 'TIMEX3']

        iob_labels = self.get_iob_labels()

        for line in iob_labels:
            for iob_tag in line:
                if iob_tag["entity_type"] != entity_type:
                    iob_tag['entity_label'] = 'O'

        return iob_labels

    def set_tlinks(self, timexEventFeats, timexEventLabels, timexEventOffsets):

        exit("set_tlinks doesn't work yet")

        # TODO: not sure if connor needs timexEventOffsets paired together. but it's there as a
        # parameter for now.

        # there should be no tlinks if this method is called.
        assert self.tlinks is None

        id_chunk_map = {}

        event_ids = set()
        timex_ids = set()

        chunks = []
        chunk = []

        id_chunks = []
        id_chunk = []

        start_entity_id = None

        for token, label in zip(timexEventFeats, timexEventLabels):

            # start of entity
            if re.search('^B_', label["entity_label"]):

                if label["entity_type"] == "EVENT":
                    event_ids.add(label["entity_id"])
                else:
                    timex_ids.add(label["entity_id"])

                if len(chunk) != 0:
                    chunks.append(chunk)
                    id_chunks.append(id_chunk)

                    assert start_entity_id not in id_chunk_map

                    id_chunk_map[start_entity_id] = chunk

                    chunk = [token]
                    id_chunk = [label["entity_id"]]

                else:
                    chunk.append(token)
                    id_chunk.append(label["entity_id"])

                start_entity_id = label["entity_id"]

            elif re.search('^I_', label["entity_label"]):

                chunk.append(token)
                id_chunk.append(label["entity_id"])

            else:
                pass

        # add doc time. this is a timex.
        # TODO: need to add features for doctime. there aren't any.
        doctime = get_doctime_timex(self.note_path)
        doctime_id = doctime.attrib["tid"]
        doctime_dict = {}

        # create dict representation of doctime timex
        for attrib in doctime.attrib:

            doctime_dict[attrib] = doctime.attrib[attrib]

        id_chunk_map[doctime_id] = [doctime_dict]

        timex_ids.add(doctime_id)

        # cartesian product of entity pairs
        entity_pairs = filter(lambda t: t[0] != t[1], list(itertools.product(event_ids, timex_ids)) +\
                                                      list(itertools.product(timex_ids, event_ids)) +\
                                                      list(itertools.product(event_ids, event_ids)) +\
                                                      list(itertools.product(timex_ids, timex_ids)))

        entity_pairs = set(entity_pairs)

        relation_count = 0

        pairs_to_link = []

        for pair in entity_pairs:

            src_id = pair[0]
            target_id = pair[1]

            # no link at all
            pairs_to_link.append({"src_entity":id_chunk_map[src_id], "src_id":src_id, "target_id":target_id, "target_entity":id_chunk_map[target_id], "rel_type":'None', "tlink_id":None})

        assert len(pairs_to_link) == len(entity_pairs)

        self.tlinks = pairs_to_link


    def get_tlinked_entities(self):

        t_links = None

        if self.annotated_note_path is not None:
            t_links = get_tlinks(self.annotated_note_path)
            make_instances = get_make_instances(self.annotated_note_path)
        else:
            print "no annotated timeml note to get tlinks from returning empty list..."
            self.tlinks = []

        temporal_relations = {}

        eiid_to_eid = {}

        for instance in make_instances:
            eiid_to_eid[instance.attrib["eiid"]] = instance.attrib["eventID"]

        gold_tlink_pairs = set()

        for t in t_links:

            link = {}

            # source
            if "eventInstanceID" in t.attrib:
                src_id = eiid_to_eid[t.attrib["eventInstanceID"]]
            else:
                src_id = t.attrib["timeID"]

            # target
            if "relatedToEventInstance" in t.attrib:
                target_id = eiid_to_eid[t.attrib["relatedToEventInstance"]]
            else:
                target_id = t.attrib["relatedToTime"]

            tmp_dict = {"target_id":target_id, "rel_type":t.attrib["relType"], "lid":t.attrib["lid"]}

            gold_tlink_pairs.add((src_id, target_id))

            if src_id in temporal_relations:


                # this would mean the same src id will map to same target with different relation type.
                # not possible.
                assert tmp_dict not in temporal_relations[src_id]

                temporal_relations[src_id].append(tmp_dict)

            else:
                temporal_relations[src_id] = [tmp_dict]

        assert( len(gold_tlink_pairs) == len(t_links) )

        event_ids = set()
        timex_ids = set()

        chunks = []
        chunk = []

        id_chunk = []
        id_chunks = []

        start_entity_id = None

        id_chunk_map = {}

        # get tagged entities and group into a list
        for sentence_num, labels in zip(self.pre_processed_text, self.get_iob_labels()):

            for token, label in zip(self.pre_processed_text[sentence_num], labels):

                # start of entity
                if re.search('^B_', label["entity_label"]):

                    if label["entity_type"] == "EVENT":
                        event_ids.add(label["entity_id"])
                    else:
                        timex_ids.add(label["entity_id"])

                    if len(chunk) != 0:
                        chunks.append(chunk)
                        id_chunks.append(id_chunk)

                        assert start_entity_id not in id_chunk_map

                        id_chunk_map[start_entity_id] = chunk

                        chunk = [token]
                        id_chunk = [label["entity_id"]]

                    else:
                        chunk.append(token)
                        id_chunk.append(label["entity_id"])

                    start_entity_id = label["entity_id"]

                elif re.search('^I_', label["entity_label"]):

                    assert label["entity_id"] == start_entity_id

                    chunk.append(token)
                    id_chunk.append(label["entity_id"])

                else:
                    pass

        if len(chunk) != 0:
            chunks.append(chunk)
            assert len(id_chunk) == len(chunk)
            id_chunks.append(id_chunk)

            assert start_entity_id not in id_chunk_map
            id_chunk_map[start_entity_id] = chunk

        chunk = []
        id_chunk = []

        assert len(event_ids.union(timex_ids)) == len(id_chunks)
        assert len(id_chunk_map.keys()) == len(event_ids.union(timex_ids))

        # TODO: need to add features for doctime. there aren't any.
        # add doc time. this is a timex.
        doctime = get_doctime_timex(self.note_path)
        doctime_id = doctime.attrib["tid"]
        doctime_dict = {}

        # create dict representation of doctime timex
        for attrib in doctime.attrib:

            doctime_dict[attrib] = doctime.attrib[attrib]

        id_chunk_map[doctime_id] = [doctime_dict]

        timex_ids.add(doctime_id)

        # cartesian product of entity pairs
        entity_pairs = filter(lambda t: t[0] != t[1], list(itertools.product(event_ids, timex_ids)) +\
                                                      list(itertools.product(timex_ids, event_ids)) +\
                                                      list(itertools.product(event_ids, event_ids)) +\
                                                      list(itertools.product(timex_ids, timex_ids)))

        entity_pairs = set(entity_pairs)

        relation_count = 0

        pairs_to_link = []

        for pair in entity_pairs:

            src_id = pair[0]
            target_id = pair[1]

            if src_id in temporal_relations:

                relation_found = False

                for target_entity in temporal_relations[src_id]:

                    if target_id == target_entity["target_id"]:

                        relation_count += 1

                        # need to assign relation to each pairing if there exists one otherwise set 'none'
                        pairs_to_link.append({"src_entity":id_chunk_map[src_id], "src_id":src_id, "target_id":target_id, "target_entity":id_chunk_map[target_id], "rel_type":target_entity["rel_type"], "tlink_id":target_entity["lid"]})

                    else:

                        pairs_to_link.append({"src_entity":id_chunk_map[src_id], "src_id":src_id, "target_id":target_id, "target_entity":id_chunk_map[target_id], "rel_type":'None', "tlink_id":None})

            else:

                # no link at all
                pairs_to_link.append({"src_entity":id_chunk_map[src_id], "src_id":src_id, "target_id":target_id, "target_entity":id_chunk_map[target_id], "rel_type":'None', "tlink_id":None})

        assert len(pairs_to_link) == len(entity_pairs)
        assert relation_count == len(t_links)

        self.tlinks = pairs_to_link

    def get_iob_labels(self):

        # don't want to modify original
        pre_processed_text = copy.deepcopy(self.pre_processed_text)

        # need to create a list of tokens
        iob_labels = []

        if self.annotated_note_path is not None:

            tagged_entities = get_tagged_entities(self.annotated_note_path)
            _tagged_entities = get_tagged_entities(self.annotated_note_path)

            raw_text_element = get_text_element(self.note_path)
            raw_text = get_raw_text(raw_text_element)

            labeled_text_element = get_text_element(self.annotated_note_path)
            labeled_text = get_raw_text(labeled_text_element)

            # TODO: cleanup
            raw_text = raw_text.strip("<TEXT>\n")
            raw_text = raw_text.strip("<\/TEXT>")

            labeled_text = labeled_text.strip("<TEXT>\n")
            labeled_text = labeled_text.strip("<\/TEXT>")

            raw_index = 0
            labeled_index = 0

            raw_char_offset = 0
            labeled_char_offset = 0

            # should we count?
            count_raw = True
            count_labeled = True

            text1 = ""
            text2 = ""

            start_count = 0
            end_count = 0

            offsets = {}

            tagged_element = None

            # need to get char based offset for each tagging within annotated timeml doc.
            while raw_index < len(raw_text) or labeled_index < len(labeled_text):

                if raw_index < len(raw_text):
                    if count_raw is True:
                        raw_char_offset += 1
                        text1 += raw_text[raw_index]
                    raw_index += 1

                if labeled_index < len(labeled_text):

                    if labeled_text[labeled_index:labeled_index+1] == '<' and labeled_text[labeled_index:labeled_index+2] != '</':

                        tagged_element = tagged_entities.pop(0)

                        count_labeled = False
                        start_count += 1

                    elif labeled_text[labeled_index:labeled_index+2] == '</':
                        count_labeled = False
                        start_count += 1

                    if labeled_text[labeled_index:labeled_index+1] == ">":

                        if tagged_element != None:

                            start = labeled_char_offset
                            end   = labeled_char_offset+len(tagged_element.text) - 1

                            # spans should be unique?
                            offsets[(start, end)] = {"tagged_xml_element":tagged_element, "text":tagged_element.text}
                            assert raw_text[start:end + 1] == tagged_element.text, "\'{}\' != \'{}\'".format( raw_text[start:end + 1], tagged_element.text)
                            tagged_element = None

                        end_count += 1
                        count_labeled = True

                        labeled_index += 1
                        continue

                    if count_labeled is True:
                        labeled_char_offset += 1
                        text2 += labeled_text[labeled_index]

                    labeled_index += 1

            # lots of checks!
            assert text1 == text2
            assert start_count == end_count, "{} != {}".format(start_count, end_count)
            assert raw_index == len(raw_text) and labeled_index == len(labeled_text)
            assert raw_char_offset == labeled_char_offset
            assert len(tagged_entities) == 0
            assert tagged_element is None
            assert len(offsets) == len(_tagged_entities)


        for sentence_num in sorted(pre_processed_text.keys()):

            # list of dicts
            sentence = pre_processed_text[sentence_num]

            # iobs in a sentence
            iobs_sentence = []

            # need to assign the iob labels by token index
            for token in sentence:

                if self.annotated_note_path is not None:
                    # set proper iob label to token

                    iob_label, entity_type, entity_id = TimeNote.get_iob_label(token, offsets)

                    if iob_label is None:
                        assert entity_id is not None

                    assert entity_type in ['EVENT', 'TIMEX3', None]

                else:

                    iob_label = 'O'

                    entity_type = None
                    entity_id = None

                iobs_sentence.append({'entity_label':iob_label,
                                      'entity_type':entity_type,
                                      'entity_id':entity_id})

            iob_labels.append(iobs_sentence)


        return iob_labels

    def get_iob_features(self):

        """ returns featurized representation of events and timexes """

        vectors = []

        for line in self.pre_processed_text:

            for token in self.pre_processed_text[line]:

                vectors.append(token)

        return vectors

    def get_tlink_ids(self):

        tlink_ids = []

        for tlink in self.tlinks:

            tlink_ids.append(tlink["tlink_id"])

        return tlink_ids

    def get_tlink_labels(self):
        """ return the labels of each tlink from annotated doc """

        tlink_labels = []

        for tlink in self.tlinks:

            tlink_labels.append(tlink["rel_type"])

        return tlink_labels

    def get_tlink_id_pairs(self):

        """ returns the id pairs of two entities joined together """

        tlink_id_pairs = []

        for tlink in self.tlinks:

            tlink_id_pairs.append((tlink["src_id"], tlink["target_id"]))

        return tlink_id_pairs

    def get_tlink_features(self):

        """ returns featurized representation of tlinks """
        vectors = []

        for relation in self.tlinks:

            vector = {}

            target_entity = relation["target_entity"]
            src_entity = relation["src_entity"]

            for i, token in enumerate(src_entity):

                # merge features of each entity together
                for key in token:

                    vector["src_token{}_".format(i) + key] = token[key]

            for i, token in enumerate(target_entity):

                for key in token:

                    vector["target_token{}_".format(i) + key] = token[key]

            vectors.append(vector)

        return vectors


    def get_token_char_offsets(self):

        """ returns the char based offsets of token.

        for each token within self.pre_processed_text iterate through list of dicts
        and for each value mapped to the key 'start_offset' and 'end_offset' create a
        list of 1-1 mappings

        Returns:
            A flat list of offsets of the token within self.pre_processed_text:

                [(0,43),...]
        """

        offsets = []

        for line_num in self.pre_processed_text:

            for token in self.pre_processed_text[line_num]:

                offsets.append((token["start_offset"], token["end_offset"]))

        return offsets

    @staticmethod
    def get_iob_label(token, offsets):

        # NOTE: never call this directly. input is tested within _read

        tok_span = (token["start_offset"], token["end_offset"])

        label = 'O'
        entity_id = None
        entity_type = None

        for span in offsets:

            if TimeNote.same_start_offset(span, tok_span):

                labeled_entity = offsets[span]["tagged_xml_element"]

                if 'class' in labeled_entity.attrib:
                    label = 'B_' + labeled_entity.attrib["class"]
                else:
                    label = 'B_' + labeled_entity.attrib["type"]

                if 'eid' in labeled_entity.attrib:
                    entity_id = labeled_entity.attrib["eid"]
                else:
                    entity_id = labeled_entity.attrib["tid"]

                entity_type = labeled_entity.tag

                break

            elif TimeNote.subsumes(span, tok_span):

                labeled_entity = offsets[span]["tagged_xml_element"]

                if 'class' in labeled_entity.attrib:
                    label = 'I_' + labeled_entity.attrib["class"]
                else:
                    label = 'I_' + labeled_entity.attrib["type"]

                if 'eid' in labeled_entity.attrib:
                    entity_id = labeled_entity.attrib["eid"]
                else:
                    entity_id = labeled_entity.attrib["tid"]

                entity_type = labeled_entity.tag

                break

        return label, entity_type, entity_id

    @staticmethod
    def same_start_offset(span1, span2):
        """
        doees span1 share the same start offset?
        """
        return span1[0] == span2[0]

    @staticmethod
    def subsumes(span1, span2):
        """
        does span1 subsume span2?
        """
        return span1[0] < span2[0] and span2[1] <= span1[1]

    def create_features_vect_tlinks(self, entity_pairs):

        # TODO: this will be done after training is completed.
        pass

def __unit_tests():

    """ basic assertions to ensure output correctness """

    t =  TimeNote("APW19980219.0476.tml.TE3input", "APW19980219.0476.tml")

    for label in t.get_timex_iob_labels():
        for token in label:

            if token['entity_type'] == 'TIMEX3':
                assert token['entity_label'] != 'O'
            else:
                assert token['entity_label'] == 'O'

    for label in t.get_event_iob_labels():
        for token in label:

            if token['entity_type'] == 'EVENT':
                assert token['entity_label'] != 'O'
            else:
                assert token['entity_label'] == 'O'

    """
    number_of_tlinks = len(t.get_tlink_features())
    assert number_of_tlinks != 0
    assert len(t.get_tlink_id_pairs()) == number_of_tlinks, "{} != {}".format(len(t.get_tlink_id_pairs()), number_of_tlinks)
    assert len(t.get_tlink_labels()) == number_of_tlinks
    assert len(t.get_tlink_ids()) == number_of_tlinks
    #print t.get_token_char_offsets()
    """

    t.get_tlink_features()

#    print t.get_iob_features()

#    print t.get_tlinked_entities()

#    print t.get_tlink_labels()

if __name__ == "__main__":

    __unit_tests()

    print "nothing to do"




