import sys
import copy
import os
import xml.etree.ElementTree as ET

from string import whitespace

def parse(naf_tagged_doc):

    xml_root = ET.fromstring(naf_tagged_doc)

    tokens             = []
    pos_tags           = []
    lemmas             = []
    main_verbs         = []
    tokens_to_offset   = {}
    named_entities     = {}
    constituency_trees = {}
    id_to_role         = {}

    for e in xml_root:

        if e.tag   == "text":
            tokens, tokens_to_offset = get_tokens(e)
        elif e.tag == "terms":
            pos_tags, lemmas = get_grammatical_info(e)
        elif e.tag == "entities":
            named_entities = get_named_entities(e)
        elif e.tag == "constituency":
            constituency_trees = get_constituency_trees(e)
        elif e.tag == "srl":
            main_verbs, id_to_role = get_srl_info(e)
        else:
            continue

    return tokens, tokens_to_offset, pos_tags, lemmas, named_entities, constituency_trees, main_verbs, id_to_role


def get_tokens(text_element):

    """Get the tokens annotated by NewsReader pipeline

    @param naf_tagged_doc: NAF annotated document generated by NewsReader pipeline
    """

    tokens = []
    tokens_to_offset = {}

    naf_tokens = []

    for e in text_element:
        naf_tokens.append(e)

    for naf_token in naf_tokens:

        sentence_num = int(naf_token.attrib["sent"])
        id_string    = naf_token.attrib["id"]

        tok_start    = int(naf_token.attrib["offset"])
        token_end    = tok_start + int(naf_token.attrib["length"]) - 1

        token_text = naf_token.text

        tokens.append({"token":token_text,
                       "id":id_string,
                       "sentence_num":sentence_num,
                       "char_start_offset":tok_start,
                       "char_end_offset":token_end})

        if token_text in tokens_to_offset:
            tokens_to_offset[token_text].append((tok_start, token_end))
        else:
            tokens_to_offset[token_text] = [(tok_start, token_end)]

    return tokens, tokens_to_offset


def get_grammatical_info(terms_element):

    """Get the pos tags and lemma of terms annotated by NewsReader pipeline.
       look here for interpreting pos taggings:

            https://www.ling.upenn.edu/courses/Fall_2003/ling001/penn_treebank_pos.html
    @param naf_tagged_doc: NAF annotated document generated by NewsReader pipeline
    """

    pos_tags = []
    lemmas   = []

    for naf_term in terms_element:

        # I think I can just change t1 to w1, seems like one to one mapping.
        id_str  = naf_term.attrib["id"].replace('t','w')

        pos_tag = naf_term.attrib["morphofeat"]
        pos_tags.append({"pos_tag":pos_tag,
                         "id":id_str})

        lemma   = naf_term.attrib["lemma"]
        lemmas.append({"lemma":lemma, "id":id_str})

    return pos_tags, lemmas


def get_named_entities(entities_element):

    taggings = {}

    references_elements =  map(lambda entity_element: entity_element[0],
                               entities_element)

    ner_span_elements =  map(lambda references_element: references_element[0],
                             references_elements)

    assert len(entities_element) == len(ner_span_elements)

    clustered_target_ids = []

    for ner_span_element in ner_span_elements:

        ids = []

        for target in ner_span_element:

            target_id = target.attrib["id"]
            target_id = list(target_id)
            target_id[0] = 'w'
            target_id = "".join(target_id)

            ids.append(target_id)

        clustered_target_ids.append(ids)

    ner_labels = []

    for entity, ids in zip(entities_element, clustered_target_ids):

        labels = {"ne_id":entity.attrib["id"], "ner_tag":entity.attrib["type"]}
        labels.update({"target_ids":ids})

        ner_labels.append(labels)


    # a list of dicts of form [ {"ner_tag":<tag>, "entity":<list of targets>}, ...]
    for mapping in ner_labels:

        ne_id =  mapping["ne_id"]
        ner_tag   =  mapping["ner_tag"]
        target_ids = mapping["target_ids"]

        for target_id in target_ids:

            assert target_id not in taggings

            taggings[target_id] = {"ne_id":ne_id,
                                   "ner_tag":ner_tag,
                                   "ne_chunk_ids":target_ids}

    return taggings


def _create_edge(constituency_parent, constituency_child):

    """ will update respective fields in each node given as input """
    constituency_parent.set_child(constituency_child)
    constituency_child.set_parent(constituency_parent)


def get_constituency_trees(constituency_element):

    trees = {}

    tree_elements = []

    for e in constituency_element:

        if e.tag == "tree":
            tree_elements.append(e)

    sentence_num = 1

    for tree in tree_elements:

        trees[sentence_num]= ConstituencyTree(tree)
        sentence_num += 1

    return trees


class ConstituencyNode(object):

     # TODO: refactor this.

    def __init__(self, xml_node):

        self.parent_node = None
        self.child_node = None

        self.node_id = xml_node.attrib["id"]
        self.target_id = None

        if 'label' in xml_node.attrib:
            self.terminal = False

            # non terminal nodes are given labels
            self.label = xml_node.attrib['label']

        else:

            # node is a terminal node
            self.terminal = True
            self.label = None

            i = 1

            # terminal node
            for span in xml_node:
                for target in span:
                    # TODO: assumption
                    # I am assuming there is only one target. if i'm wrong all the code
                    # i have writen is wrong and it will be good to know this in the future.
                    assert( i < 2 )
                    self.target_id = target.attrib["id"].replace('t', 'w')
                    i += 1

    def is_terminal_node(self):

        return self.terminal

    def get_target_id(self):

        return self.target_id

    def get_id(self):

        return self.node_id

    def get_label(self):

        return self.label

    """
    def __repr__(self):

        # for debugging purposes
        return "terminal?: {}, id: {}, label: {}, target id: {}\n".format(self.is_terminal_node(), self.get_id(), self.get_label(), self.get_target_ids())
    """

    def set_child(self, node):
        # can have multiple parents
        if self.child_node is None:
            self.child_node = [node]
        else:
            self.child_node.insert(0, node)

    def set_parent(self, node):
        # only one parent
        if self.parent_node is None:
            self.parent_node = node
        else:
            exit( "more than one parent? something bad has happened" )

    def has_child(self):
        return self.child_node is not None

    def is_child(self):

        return self.parent_node is not None

    def is_root(self):

        return self.parent_node is None

    def get_parent(self):

        return self.parent_node


class ConstituencyTree(object):


    def __init__(self, xml_constituency_tree_element):

        self.terminal_nodes = self.process_constituency_tree_element(xml_constituency_tree_element)


    def process_constituency_tree_element(self, xml_constituency_tree_element):
        """ generates a tree structure to determine the categories each token belongs in. """

        #print "called create_constituency_nodes"
        constituency_nodes = {}
        terminal_nodes = {}

        # used to assert if there can be same target id in different nodes
        target_ids_seen = set()

        """ the elements within the xml tree element is sequential, i think. just proces them in order """
        for element in xml_constituency_tree_element:

            if element.tag == 'nt' or element.tag == 't':
                node = ConstituencyNode( element )
                constituency_nodes[node.get_id()] = node

                if node.is_terminal_node():
                    terminal_nodes[node.get_target_id()] = node
                    if node.get_target_id() in target_ids_seen:
                        # TODO: im making an assumption. if this comes back to bite me then i need to redo this.
                        exit("error: target already seen...")
                    else:
                        target_ids_seen.add(node.get_target_id())

            elif element.tag == 'edge':
                #print "TODO: handle edge"

                parent_id = element.attrib["to"]
                child_id  = element.attrib["from"]

                parent_node = constituency_nodes[parent_id]
                child_node  = constituency_nodes[child_id]

                # update fields of each node to create edge.
                _create_edge(parent_node, child_node)

        return terminal_nodes


    def get_parenthetical_tree(self, sentence):
        '''
        wrapper around _get_parenthetical_tree_for_subtree that generates parenthetical tree for the entire tree by starting at the root.
        The sentence parameter is sentence the constituency tree corresponds to. It is used to place the raw token in the correct position in the
        final string.
        '''

        root = None

        # choose an arbitrary node
        node = self.terminal_nodes[self.terminal_nodes.keys()[0]]

        # follow node parent paths until root node is reached
        while node.is_root() is False:
            node = node.parent_node

        root = node

        assert root.is_root() is True

        return self._get_parenthetical_tree_for_subtree(root, sentence)

    def _get_parenthetical_tree_for_subtree(self, root, sentence):
        '''
        Creates a string representation of the constituency tree, using parenthesis to represent each node.
        This is generated recursively, with a pre-order recurvise traversal of the constituency tree.
        The sentence parameter is sentence the constituency tree corresponds to. It is used to place the raw token in the correct position in the final string.
        '''

        parenthetical_tree = ''

        #Assumption: children are stored in reverse order of appearance in the setence. Will cause problems if this doens't prove correct
        for child in reversed(root.child_node):

            if child.is_terminal_node() is False:
                parenthetical_tree += '(' + child.get_label()

                assert child.has_child() is True

                parenthetical_tree += ' ' + self._get_parenthetical_tree_for_subtree(child, sentence) + ')'

            else:
                word = next((token for token in sentence if token['id'] == child.get_target_id()), None)

                assert word is not None

                # store ) and ( differently since they are used as boundary characters
                if word is ')':
                    parenthetical_tree += '-RRB-'
                elif word is '(':
                    parenthetical_tree += '-LRB'
                else:
                    parenthetical_tree += word['token']

                parenthetical_tree += ')'

        return parenthetical_tree


    def get_phrase_memberships(self, node_id):

        assert( node_id in self.terminal_nodes )

        terminal_node = self.terminal_nodes[node_id]

        level = 0

        grammar_category = {}

        # skip first node, terminal node, no labels available
        node = terminal_node.get_parent()

        # a terminal node should always have a parent.
        assert( node is not None )

        # want to get labels of all non terminal nodes.
        while node.is_root() is False:
            grammar_category[level] = node.get_label()
            level += 1
            node = node.get_parent()

        return grammar_category


def get_srl_info(srl_element):

    main_verbs = []

    # token id to its semantic role and
    id_to_role = {}

    for predicate in srl_element:

        span = []

        # i'm assuming all elements within srl_element are predicates
        assert predicate.tag == "predicate"

        preposition = None

        for element in predicate:

            if element.tag == "span":

                assert preposition is None

                span = list(element)

                assert len(span) == 1

                preposition = span[0].attrib["id"]
                preposition = list(preposition)
                preposition[0] = 'w'
                preposition = "".join(preposition)

                main_verbs.append(preposition)

            if element.tag == "role":

                role = element

                target_ids = None

                for e in role:

                    if e.tag == "span":

                        target_ids = list(e)

                        break

                predicates_ids = []
                role_ids = []

                for i in target_ids:

                    tok_id = list(i.attrib["id"])
                    tok_id[0] = 'w'
                    tok_id = "".join(tok_id)

                    is_head = False

                    if "head" in i.attrib:
                        if i.attrib["head"] == "yes": is_head = True

                    if tok_id not in id_to_role:

                        id_to_role[tok_id] = {"predicate_ids":[predicate.attrib["id"]],
                                              "role_id":[role.attrib["id"]],
                                              "semantic_role":[role.attrib["semRole"]],
                                              "head_token":[is_head],
                                              "toks_preposition":[preposition]}

                    else:

                        id_to_role[tok_id]["predicate_ids"].append(predicate.attrib["id"])
                        id_to_role[tok_id]["role_id"].append(role.attrib["id"])
                        id_to_role[tok_id]["semantic_role"].append(role.attrib["semRole"])
                        id_to_role[tok_id]["head_token"].append(is_head),
                        id_to_role[tok_id]["toks_preposition"].append(preposition)

    return main_verbs, id_to_role


def strip_quotes(text):
    """ the pipeline we use does really weird stuff to quotes. just going to remove them for now or forever """

    text     = re.sub(r"``", r"''", text)
    text     = re.sub(r'"', r"'", text)

    return text


def get_root(xml_doc_path):

    valid_path(xml_doc_path)

    tree = ET.parse(xml_doc_path)
    root = tree.getroot()

    return root


def get_raw_text(xml_tree_element):
    """ get raw text with xml encodings a string """

    text =  ET.tostring(xml_tree_element)

    return text


def write_root_to_file(xml_root, file_path):

    tree = ET.ElementTree(xml_root)

    print file_path
    tree.write(file_path, xml_declaration=True, encoding="us-ascii")


class DependencyPath(object):

    def __init__(self, ixa_tok_output):

        self.deps = self._get_deps(ixa_tok_output)


    def get_paths(self, token_id1, token_id2):
        """
        Wrapper to initialize a global cache of seen tokens to prevent infinite recursion
        """

        self.seen = set()

        # tokens don't appear. no dependencies.
        if token_id1 not in self.deps and token_id2 not in self.deps:
            print "no dependencies available between tokens..."
            return []

        paths = self._get_paths(token_id1, token_id2)
        paths += self._get_paths(token_id2, token_id1)

        self.seen = set()

        # remove paths with no end markers (invalid paths)
        paths = filter(lambda p: p[-1] == "END", paths)

        # inplace order paths by increasing order by len
        paths.sort(key=lambda p: len(p))

        # get the shortest path. omit the END marker
        return paths[0][:-1]

    def _get_paths(self, token_id1, token_id2):
        """
        Go through dependencies extracted from _get_deps and try and find smallest paths
        between two tokens.

        Expects to take in the token id (t##)
        """
        paths = []

        # reach desired end!
        if token_id1 == token_id2:
            return [["END"]]
        # cycle? or end? (not desired end!)
        elif token_id1 in self.seen or token_id1 not in self.deps:
            return [[None]]

        self.seen.add(token_id1)

        for token_id in self.deps[token_id1]:
            paths += [[(token_id1, token_id, self.deps[token_id1][token_id])] + p for p in self._get_paths(token_id, token_id2)]

        return paths


    def _get_deps(self, ixa_pipe_output):
        """
        Extract from the deps element in the annotated NAF file the dependencies as they appear.
        Place these dependencies within a dictionary.
        """

        xml_root = xml_root = ET.fromstring(ixa_pipe_output)

        deps_element = None

        # get deps xml element
        for e in xml_root:
            if e.tag == "deps":
                deps_element = e
                break

        deps = {}

        # get deps
        for d in deps_element:

            # d = ( [ list of tokens representing path ], [ list of rfuncs ] )
            _from  = d.attrib["from"]
            _to    = d.attrib["to"]
            _rfunc = d.attrib["rfunc"]

            if _from in deps:
                deps[_from].update({_to:_rfunc})
            else:
                deps[_from] = {_to:_rfunc}

        return deps


if __name__ == "__main__":

    d = DependencyPath(open("test.xml","rb").read())
    print d.get_paths("t12","t1")
    print d.get_paths("t56","t60")
    print d.get_paths("t32", "t38")
