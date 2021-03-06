from flua.Compiler.Output.BaseNamespace import *

class BaseEnvironment:
	
	def __init__(self, action):
		self.name = "None"
		self.rootDir = ""
		self.mainNamespace = BaseNamespace("")
		self.fileExtensions = {}
		self.standardFileExtension = ""
		self.autoCompleteKeywords = {}
		self.highlightKeywords = {}
		self.singleLineCommentIndicators = {}
		self.preprocessorIndicators = {}
		self.internalDataTypes = {}
		self.internalFunctions = {}
		self.specialKeywords = {}
		self.selfReferences = {}
		self.action = action
		
		self.operators = {
			'=',
			# Comparison
			'==', '!=', '<', '<=', '>', '>=',
			# Arithmetic
			'\+', '-', '\*', '/', '//', '\%', '\*\*', '\^',
			# In-place
			'\+=', '-=', '\*=', '/=', '\%=',
			# Bitwise
			'\^', '\|', '\&', '\~', '>>', '<<',
			# Data Flow
			'<-', '->', '<--', '-->',
			# Type declaration
			':',
			# Tilde
			'~',
		}
		
		self.braces = {
			'(', ')', '[', ']', '{', '}',
		}
