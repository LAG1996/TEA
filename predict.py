import os
import cPickle
import argparse

os.environ["TEA_PATH"] = os.getcwd()
os.environ["PUNKT_PATH"] = os.environ["TEA_PATH"] + "/data/nltk_data/tokenizers/punkt/english.pickle"

from code.notes.TimeNote import TimeNote

from code import model

def main():

	parser = argparse.ArgumentParser()
	parser.add_argument("model", help="Model file to use in prediction")
	parser.add_argument("predictList", metavar='Predict List', nargs='+', 
		help="The list of files to annotate.")
	args = parser.parse_args()
	
	modfile = args.model
	files = args.predictList

	#load data from files
	notes = []

	#read in files as notes
	for tml in files:
		tmp_note = TimeNote(tml)
		notes.append(tmp_note)

	with open(modfile) as modelfile:
		model = cPickle.load(modelfile)

	labels = predictWithModel(notes, model)

	writeAnnotatedFile(labels)

def predictWithModel(notes, model):
	
	timexLabels = []
	eventLabels = []
	relationsLabels = []

	timexLabels, eventLabels = model.predict(notes)

	print timexLabels
	print eventLabels
	return {"TIMEX3":timexLabels, "EVENT":eventLabels, "TLINK":relationsLabels}

def writeAnnotatedFile(labels):
	pass

if __name__ == '__main__':
	main()