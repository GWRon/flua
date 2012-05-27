####################################################################
# Header
####################################################################
# File:		Base class for output files
# Author:   Eduard Urbach

####################################################################
# License
####################################################################
# (C) 2012  Eduard Urbach
# 
# This file is part of Blitzprog.
# 
# Blitzprog is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Blitzprog is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Blitzprog.  If not, see <http://www.gnu.org/licenses/>.

####################################################################
# Imports
####################################################################
from bp.Compiler.Utils import *
from bp.Compiler.Config import *
from bp.Compiler.Output import *
from bp.Compiler.Input.bpc.BPCUtils import *

####################################################################
# Globals
####################################################################
INT32_MAX = 2147483647
INT32_MIN = -2147483648

enableOperatorOverloading = {
	"add",
	"equal",
	"not-equal",
	"multiply"
}#{"add", "subtract", "multiply", "divide", "equal"}:

replacedNodeValues = {
	"from" : "_from",
}

####################################################################
# Classes
####################################################################
class BaseOutputFile(ScopeController):
	
	def __init__(self, compiler, file, root):
		ScopeController.__init__(self)
		
		self.compiler = compiler
		self.file = fixPath(file)
		self.dir = extractDir(file)
		
		# XML
		self.root = root
		self.codeNode = getElementByTagName(self.root, "code")
		self.headerNode = getElementByTagName(self.root, "header")
		self.dependencies = getElementByTagName(self.headerNode, "dependencies")
		self.strings = getElementByTagName(self.headerNode, "strings")
		
		# Local
		self.localClasses = []
		self.localFunctions = []
		self.additionalCodePerLine = []
		
		# Increment id
		self.compiler.fileCounter += 1
		self.id = "file_" + str(self.compiler.fileCounter)
		
		# Current
		self.currentClass = self.compiler.mainClass
		self.currentClassImpl = self.currentClass.requestImplementation([], [])
		self.currentFunction = None
		self.currentFunctionImpl = None
		
		# State
		self.inExtern = 0
		self.inGetter = 0
		self.inSetter = 0
		self.inCastDefinition = 0
		self.inTemplate = 0
		self.inAssignment = 0
		self.inConst = 0
		self.inUnmanaged = 0
		self.inOperators = 0
		self.inCasts = 0
		self.inOperator = 0
		self.inTypeDeclaration = 0
		self.inFunction = 0
		self.inDefine = 0
		self.inExtends = 0
		self.inParallel = 0
		self.inShared = 0
		self.namespaceStack = []
		self.parallelBlockStack = []
		
		# TODO: Read from module meta data
		# Speed / Correctness
		self.checkDivisionByZero = True#self.compiler.checkDivisionByZero
		
		# Inserted for mathematical expressions
		self.exprPrefix = ""
		self.exprPostfix = ""
		
		# String class
		self.stringClassDefined = False
		
		# Syntax
		self.lineLimiter = ""
		self.myself = ""
		self.trySyntax = ""
		self.catchSyntax = ""
		self.returnSyntax = ""
		self.memberAccessSyntax = ""
		self.singleParameterSyntax = ""
		self.parameterSyntax = ""
		self.newObjectSyntax = ""
		self.binaryOperatorSyntax = "%s%s%s%s%s"
		self.binaryOperatorDivideSyntax = "%s%s%s%s%s"
		self.pointerDerefAssignSyntax = ""
		self.assignSyntax = "%s = %s"
		self.assignFirstTimeSyntax = self.assignSyntax
		self.constAssignSyntax = ""
		self.callSyntax = "%s(%s)"
		self.externCallSyntax = self.callSyntax
		
		# Memory management
		self.useGC = True
		
		# Debugging
		self.lastParsedNode = list()
	
	def compile(self):
		raise NotImplementedError()
	
	def createVariable(self, name, type, value, isConst, isPointer, isPublic):
		raise NotImplementedError()
	
	def castToNativeNumeric(self, variableType, value):
		return value
	
	def checkStringClass(self):
		# Implement operator = of the string class manually to enable assignments
		if self.compiler.needToInitStringClass:
			#self.implementFunction("UTF8String", correctOperators("="), ["~MemPointer<ConstChar>"])
			self.implementFunction("UTF8String", "init", [])
			self.implementFunction("UTF8String", "init", ["~MemPointer<Byte>"])
			self.compiler.needToInitStringClass = False
		
		if self.classExists("UTF8String") and self.stringClassDefined == False:
			self.compiler.needToInitStringClass = True
	
	def handleAssign(self, node):
		self.inAssignment += 1
		isSelfMemberAccess = False
		
		# Member access (setter)
		op1 = node.childNodes[0].childNodes[0]
		if not isTextNode(op1):
			if op1.tagName == "access":
				accessOp1 = op1.childNodes[0].childNodes[0]
				accessOp2 = op1.childNodes[1].childNodes[0]
				
				# data access from a pointer
				accessOp1Type = self.getExprDataType(accessOp1)
				if extractClassName(accessOp1Type) == "MemPointer" and accessOp2.nodeValue == "data": #and isUnmanaged(accessOp1Type):
					return self.pointerDerefAssignSyntax % (self.parseExpr(accessOp1), self.parseExpr(node.childNodes[1]))
				
				isMemberAccess = self.isMemberAccessFromOutside(accessOp1, accessOp2)
				if isMemberAccess:
					#print("Using setter for type '%s'" % (accessOp1type))
					setFunc = parseString("<call><function><access><value>%s</value><value>%s</value></access></function><parameters><parameter>%s</parameter></parameters></call>" % (accessOp1.toxml(), "set" + capitalize(accessOp2.nodeValue), node.childNodes[1].childNodes[0].toxml())).documentElement
					return self.handleCall(setFunc)
				#pass
				#variableType = self.getExprDataType(op1)
				#variableClass = self.compiler.classes[removeGenerics(variableType)]
			elif op1.tagName == "index":
				return self.parseExpr(node.childNodes[0]) + " = " + self.parseExpr(node.childNodes[1])
		
		# Inline type declarations
		declaredInline = (tagName(node.childNodes[0].childNodes[0]) == "declare-type")
		
		# Inline declaration + top level scope = don't include type name
		variableName = self.getNamespacePrefix()
		if declaredInline and self.getCurrentScope() == self.getTopLevelScope():
			variableName += self.handleTypeDeclaration(node.childNodes[0].childNodes[0], insertTypeName = False)
		else:
			variableName += self.parseExpr(node.childNodes[0].childNodes[0])
		
		# In parameter definition?
		if node.parentNode.tagName == "parameter":
			return variableName
		
		# Parse value
		value = self.parseExpr(node.childNodes[1].childNodes[0], False)
		
		# Parse value type
		valueType = self.getExprDataType(node.childNodes[1].childNodes[0])
		if valueType == "void":
			raise CompilerException("'%s' which is assigned to '%s' does not return a value (void)" % (value, variableName))
		
		memberName = variableName
		
		# Did we define a type?
		try:
			variableType = self.getVariableTypeAnywhere(variableName)
		except:
			variableType = ""
		
		# Member access?
		if variableName.startswith(self.memberAccessSyntax):
			memberName = variableName[len(self.memberAccessSyntax):]
			isSelfMemberAccess = True
		
		if isSelfMemberAccess:
			var = self.createVariable(memberName, valueType, value, self.inConst, not valueType in nonPointerClasses, False)
			#if not variableName in self.currentClass.members:
			#	self.currentClass.addMember(var)
			
			if not memberName in self.currentClassImpl.members:
				self.currentClassImpl.addMember(var)
			
			variableExisted = True
		else:
			variableExisted = self.variableExistsAnywhere(variableName)
		
		# Need to register it here?
		if not variableExisted and not declaredInline:
			var = self.createVariable(variableName, valueType, value, self.inConst, not valueType in nonPointerClasses, False)
			self.registerVariable(var)
			
			if self.inConst:
				if self.getCurrentScope() == self.getTopLevelScope():
					return ""
				else:
					return self.constAssignSyntax % (var.getFullPrototype(), value)
		
		#else:
		#	var = self.getVariableTypeAnywhere(variableName)
		
		#if not variable in self.currentClassImpl.members:
		#	self.currentClassImpl.add
		
		# Int = BigInt
		if variableType in {"Int", "Int32", "Int64"} and valueType == "BigInt":
			value = self.castToNativeNumeric(variableType, value)
		
		self.inAssignment -= 1
		
		#print(node.toprettyxml())
		#print(variableName, "|", variableType, "|", value, "|", valueType)
		
		# Casts
		if variableExisted and variableType and variableType != valueType and not valueType in nonPointerClasses and not extractClassName(valueType) == "MemPointer":
			debug("Need to cast %s to %s" % (valueType, variableType))
			#if variableType in nonPointerClasses:
			#	castType = "static_cast"
			#else:
			#	castType = "reinterpret_cast"
			value = "((%s)%sto%s())" % (value, self.ptrMemberAccessChar, normalizeName(variableType))
		
		# Unmanaged types
		if isUnmanaged(valueType) and not variableExisted:
			#print(variableName, " : ", variableType, " ||| ", value, " : ", valueType)
			return self.declareUnmanagedSyntax % (var.getPrototype(), value)
		elif self.getCurrentScope() == self.getTopLevelScope():
			return self.assignSyntax % (variableName, value)
		elif variableExisted:
			return self.assignSyntax % (variableName, value)
		elif declaredInline:
			return self.assignSyntax % (variableName, value) #+ ";//Declared inline"
		else:
			return self.assignFirstTimeSyntax % (var.getPrototype(), value)
	
	def parseBinaryOperator(self, node, connector, checkPointer = False):
		op1 = self.parseExpr(node.childNodes[0].childNodes[0])
		op2 = self.parseExpr(node.childNodes[1].childNodes[0])
		
		if op2 == "my":
			op2 = self.myself
		
		if op1 == "my":
			op1 = self.myself
		
#		if checkPointer:
#			op1type = self.getExprDataType(node.childNodes[0].childNodes[0])
#			print("%s%s%s (%s)" % (op1, connector, op2, op1 + " is a '" + op1type + "'"))
#			if (not op1type in nonPointerClasses) and (not isUnmanaged(op1type)) and (not connector == " == "):
#				return self.exprPrefix + op1 + "->operator" + connector.replace(" ", "") + "(" + op2 + ")" + self.exprPostfix
		
		# Division by zero
		if self.checkDivisionByZero and (connector == " / " or connector == " \\ "):
			self.addDivisionByZeroCheck(op2)
		
		# Float conversion if needed
		if connector != " / ":
			return self.binaryOperatorSyntax % (self.exprPrefix, op1, connector, op2, self.exprPostfix)
		else:
			return self.binaryOperatorDivideSyntax % (self.exprPrefix, op1, connector, op2, self.exprPostfix)
	
	def getNamespacePrefix(self):
		namespacePrefix = '_'.join(self.namespaceStack)
		if namespacePrefix:
			return namespacePrefix + "_"
		else:
			return ""
	
	def handleCompilerFlag(self, node):
		return ""
	
	def getParameterDefinitions(self, pNode, types, defaultValueTypes):
		if pNode is None:
			return "", ""
		
		pList = ""
		funcStartCode = ""
		counter = 0
		typesLen = len(types)
		
		for node in pNode.childNodes:
			#if isElemNode(node.childNodes[0]) and node.childNodes[0].tagName == "declare-type":
			#	name = node.childNodes[0].childNodes[0].childNodes[0].nodeValue
			#else:
			name = self.parseExpr(node.childNodes[0])
			#print("Name: " + name)
			#print(node.toprettyxml())
			
			if name in replacedNodeValues:
				name = replacedNodeValues[name]
			
			# Not enough parameters
			if counter >= typesLen:
				# Default values?
				if counter < len(defaultValueTypes) and defaultValueTypes[counter]:
					defaultValueType = defaultValueTypes[counter]
					adjustedDefaultValueType = self.adjustDataType(defaultValueType)
					#print("Using default parameter of type %s translated to %s" % (defaultValueType, adjustedDefaultValueType))
					self.getCurrentScope().variables[name] = self.createVariable(name, adjustedDefaultValueType, "", False, not adjustedDefaultValueType in nonPointerClasses, False)
					pList += self.buildSingleParameter(adjustedDefaultValueType, name) + ", "
					continue
				
				raise CompilerException("You forgot to specify the parameter '%s' of the function '%s'" % (name, self.currentFunction.getName()))
			
			usedAs = types[counter]
			
			# Typedefs
			usedAs = self.prepareTypeName(usedAs)
			
			# TODO: ...
			if name.startswith(self.memberAccessSyntax):
				member = name[len(self.memberAccessSyntax):]
				self.currentClassImpl.addMember(self.createVariable(member, usedAs, "", False, not usedAs in nonPointerClasses, False))
				name = "__" + member
				funcStartCode += "\t" * self.currentTabLevel + self.memberAccessSyntax + member + " = " + name + self.lineLimiter
			
			declaredInline = (tagName(node.childNodes[0]) == "declare-type")
			if not declaredInline:
				#print("Variable %s used as '%s'" % (name, usedAs))
				self.getCurrentScope().variables[name] = self.createVariable(name, usedAs, "", False, not usedAs in nonPointerClasses, False)
				pList += self.buildSingleParameter(self.adjustDataType(usedAs), name) + ", "
			else:
				#for member in self.currentClassImpl.members.values():
				#	print(member.name)
				#	print(member.type)
				
				definedAs = self.parseExpr(node.childNodes[0].childNodes[1], True) #self.getVariableTypeAnywhere(name)
				
				# Typedefs
				definedAs = self.prepareTypeName(definedAs)
				
				definedAs = self.currentClassImpl.translateTemplateName(definedAs)
				definedAs = self.addMissingTemplateValues(definedAs)
				
				#print("Defined: " + definedAs)
				#print(name)
				#print("------------")
				
				pList += self.buildSingleParameter(self.adjustDataType(definedAs), name) + ", "
				
				if definedAs != usedAs:
					if definedAs in nonPointerClasses and usedAs in nonPointerClasses:
						heavier = getHeavierOperator(definedAs, usedAs)
						if usedAs == heavier:
							compilerWarning("Information might be lost by converting '%s' to '%s' for the parameter '%s' in the function '%s'" % (usedAs, definedAs, name, self.currentFunction.getName()))
					else:
						raise CompilerException("'%s' expects the type '%s' where you used the type '%s' for the parameter '%s'" % (self.currentFunction.getName(), definedAs, usedAs, name))
			
			counter += 1
		
		return pList[:len(pList)-2], funcStartCode
	
	def scanTemplate(self, node):
		pNames, pTypes, pDefaultValues, pDefaultValueTypes = self.getParameterList(node)
		self.currentClass.setTemplateNames(pNames, pDefaultValues)
		if self.currentClass.forceImplementation:
			self.currentClass.checkDefaultImplementation()
	
	def scanExtends(self, node):
		pNames, pTypes, pDefaultValues, pDefaultValueTypes = self.getParameterList(node)
		self.currentClass.setExtends([self.getClass(className) for className in pNames])
	
	def scanClass(self, node):
		name = getElementByTagName(node, "name").childNodes[0].nodeValue
		extendingClass = False
		
		self.pushScope()
		
		if name in self.compiler.mainClass.classes:
			refClass = self.compiler.mainClass.classes[name]
			extendingClass = True
			oldClass = self.currentClass
			self.currentClass = refClass
		else:
			refClass = self.createClass(name, node)
			if refClass.isDefaultVersion:
				self.compiler.specializedClasses[refClass.getFinalName()] = refClass
			self.pushClass(refClass)
			self.localClasses.append(self.currentClass)
		
		self.scanAhead(getElementByTagName(node, "code"))
		
		if extendingClass:
			self.currentClass = oldClass
		else:
			self.popClass()
		self.popScope()
	
	# Typedefs
	def scanDefine(self, node):
		defineWhat = self.parseExpr(node.firstChild.firstChild)
		defineAs = self.parseExpr(node.childNodes[1].firstChild)
		self.compiler.defines[defineWhat] = defineAs
	
	def scanFunction(self, node):
		if self.inCastDefinition:
			name = self.parseExpr(getElementByTagName(node, "to").childNodes[0], True)
			
			# Replace typedefs
			name = self.prepareTypeName(name)
		else:
			#print(node.toprettyxml())
			name = getElementByTagName(node, "name").childNodes[0].nodeValue
		
		#if self.inGetter:
		#	getElementByTagName(node, "name").childNodes[0].nodeValue = name = "get" + capitalize(name)
		#elif self.inSetter:
		#	getElementByTagName(node, "name").childNodes[0].nodeValue = name = "set" + capitalize(name)
		# Index operator
		name = correctOperators(name)
		
		newFunc = self.createFunction(node)
		paramNames, paramTypesByDefinition, paramDefaultValues, paramDefaultValueTypes = self.getParameterList(getElementByTagName(node, "parameters"))
		newFunc.paramNames = paramNames
		newFunc.paramTypesByDefinition = paramTypesByDefinition
		newFunc.paramDefaultValues = paramDefaultValues
		newFunc.paramDefaultValueTypes = paramDefaultValueTypes
		#debug("Types:" + str(newFunc.paramTypesByDefintion))
		self.currentClass.addFunction(newFunc)
		
		if self.currentClass.name == "":
			self.localFunctions.append(newFunc)
		
		if isMetaDataTrue(getMetaData(node, "force-implementation")):
			newFunc.setForceImplementation(True)
		
	def scanExternFunction(self, node):
		name = getElementByTagName(node, "name").childNodes[0].nodeValue
		types = node.getElementsByTagName("type")
		type = "void"
		
		if types:
			type = types[0].childNodes[0].nodeValue
		
		# TODO: Remove hardcoded
		if type == "CString":
			type = "~MemPointer<Byte>"
		
		# Typedefs
		type = self.prepareTypeName(type)
		
		self.compiler.mainClass.addExternFunction(name, type)
	
	def handleNew(self, node):
		typeName = self.parseExpr(getElementByTagName(node, "type").childNodes[0], True)
		paramsNode = getElementByTagName(node, "parameters")
		paramsString, paramTypes = self.handleParameters(paramsNode)
		
		typeName = self.prepareTypeName(typeName)
		
		pos = typeName.find("<")
		if pos != -1:
			className = removeUnmanaged(typeName[:pos])
			classObj = self.getClass(className)
			
			# Actor
			if className == "Actor":
				actorBoundClass = extractClassName(typeName[pos+1:-1])
				self.compiler.mainClass.classes[actorBoundClass].usesActorModel = True
			elif className == "MemPointer":
				ptrType = typeName[pos+1:-1]
				if len(paramsNode.childNodes) > 1:
					raise CompilerException("Too many parameters for the MemPointer constructor (only size needed)")
				
				#if ptrType in self.currentTemplateParams:
				#	ptrType = self.currentTemplateParams[ptrType]
				
				ptrType = self.currentClassImpl.translateTemplateName(ptrType)
				ptrType = self.adjustDataType(ptrType, True)
				
				if self.inUnmanaged:
					return self.buildUnmanagedMemPtrWithoutGC(ptrType, paramsString)
				elif self.useGC:
					return self.buildUnmanagedMemPtrWithGC(ptrType, paramsString)
				else:
					raise CompilerException("To create a manageable object you need to enable the GC")
		else:
			classObj = self.getClass(typeName)
			typeName = self.addMissingTemplateValues(typeName)
		
		# Mutable / Immutable
		if classObj.name in self.compiler.specializedClasses:
			classObj = self.compiler.specializedClasses[classObj.name]
		
		# Default parameters for init
		paramTypes, paramsString = self.addDefaultParameters(typeName, "init", paramTypes, paramsString)
		
		funcImpl = self.implementFunction(typeName, "init", paramTypes)
		
		if "finalize" in classObj.functions:
			destructorImpl = self.implementFunction(typeName, "finalize", [])
		
		finalTypeName = self.adjustDataType(typeName, False)
		
		if self.inUnmanaged:
			return paramsString
			#return finalTypeName + "(" + paramsString + ")"
		else:
			if self.useGC:
				# Classes are automatically managed by the GC
				return self.buildNewObject(finalTypeName, funcImpl, paramsString)
			#elif self.useReferenceCounting:
			#	return pointerType + "< " + finalTypeName + " >(new " + finalTypeName + "(" + paramsString + "))"
			#else:
			#	return "(new " + finalTypeName + "(" + paramsString + "))"
	
	def pushClass(self, classObj):
		self.currentClass.addClass(classObj)
		self.currentClass = classObj
		
	def popClass(self):
		self.currentClass = self.currentClass.parent
	
	def getLastParsedNode(self):
		if not self.lastParsedNode:
			return None
		
		return self.lastParsedNode[-1]
	
	def getExprDataType(self, node):
		dataType = self.getExprDataTypeClean(node)
		dataType = self.addMissingTemplateValues(dataType)
		
		# Replace typedefs
		dataType = self.prepareTypeName(dataType)
		
		return dataType#self.currentClassImpl.translateTemplateName(dataType)
	
	def getCallDataType(self, node):
		caller, callerType, funcName = self.getFunctionCallInfo(node)
		params = getElementByTagName(node, "parameters")
		paramsString, paramTypes = self.handleParameters(params)
		
		#if funcName == "distance":
		#	debugStop()
		#print(caller, callerType, funcName)
		if self.compiler.mainClass.hasExternFunction(funcName):
			return self.compiler.mainClass.externFunctions[funcName]
		else:
			callerClassImpl = self.getClassImplementationByTypeName(callerType)
			funcImpl = self.implementFunction(callerType, funcName, paramTypes)
			
			#raise CompilerException("Function '" + funcName + "' has not been defined  [Error code 4]")
			
			debug("Return types: " + str(funcImpl.returnTypes))
			#debug(self.compiler.funcImplCache)
			debug("Return type of '%s' is '%s' (callerType: '%s')" % (funcImpl.getName(), funcImpl.getReturnType(), callerType))
			
			return funcImpl.getReturnType()
	
	def addMissingTemplateValues(self, typeName):
		pos = typeName.find("<")
		
		if pos == -1:
			if typeName in self.compiler.mainClass.classes:
				classObj = self.getClass(typeName)
				if classObj.templateNames:
					typeName += "<"
					for dataType in classObj.templateDefaultValues:
						dataType = self.currentClassImpl.translateTemplateName(dataType)
						typeName += self.addMissingTemplateValues(dataType) + ", "
					typeName = typeName[:-2] + ">"
		else:
			pass
			#templateValues = typeName[pos+1:-1].split(",")
			#for templateValue in templateValues:
			#	templateValue = templateValue.strip()
			#	print(templateValue)
		return typeName
	
	def getExprDataTypeClean(self, node):
		if isTextNode(node):
			if node.nodeValue.isdigit():
				num = int(node.nodeValue)
				if num > INT32_MAX or num < INT32_MIN:
					return "BigInt"
				else:
					return "Int"
			elif node.nodeValue.startswith("0x"):
				return "Int"
			elif node.nodeValue.replace(".", "").isdigit():
				return "Float"
			elif node.nodeValue.startswith("bp_string_"):
				if self.stringClassDefined:
					# All modules that import UTF8String have it defined
					return "UTF8String"
				else:
					# Modules who are compiled before that have to live with CStrings
					return "~MemPointer<ConstChar>"
			elif node.nodeValue == "true" or node.nodeValue == "false":
				return "Bool"
			elif node.nodeValue == "my":
				return self.currentClassImpl.getName()
			#elif node.nodeValue == "null":
			#	return "~MemPointer<void>"
			else:
				nodeName = node.nodeValue
				if nodeName in replacedNodeValues:
					nodeName = replacedNodeValues[nodeName]
				
				return self.getVariableTypeAnywhere(nodeName)
		else:
			# Binary operators
			if node.tagName == "new":
				typeNode = getElementByTagName(node, "type").childNodes[0]
				
				if isTextNode(typeNode):
					typeName = typeNode.nodeValue
				else:
					# Template parameters
					typeName = self.parseExpr(typeNode, True)
					
				# Check defines
				typeName = self.prepareTypeName(typeName)
					
				return typeName
					#return typeNode.childNodes[0].childNodes[0].nodeValue
			elif node.tagName == "call":
				if self.inFunction:
					# Recursive functions: Try to guess
					if self.currentFunction and getElementByTagName(node, "function").childNodes[0].nodeValue == self.currentFunction.getName():
						if self.currentFunctionImpl.returnTypes:
							return self.currentFunctionImpl.getReturnType()
						else:
							raise CompilerException("Unknown data type for recursive call: " + self.currentFunction.getName())
				
				return self.getCallDataType(node)
			elif node.tagName == "assign":
				#op1 = node.childNodes[0].childNodes[0]
				op2 = node.childNodes[1].childNodes[0]
				# TODO: Check for declare-type in op1
				return self.getExprDataType(op2)
			elif node.tagName == "access":
				caller = node.childNodes[0].childNodes[0]
				
				if caller.nodeType == Node.TEXT_NODE and caller.nodeValue in self.currentClass.namespaces:
					#callerType = "bp_Namespace"
					#callerClassName = "bp_Namespace"
					varName = caller.nodeValue + "_" + node.childNodes[1].childNodes[0].nodeValue
					return self.getVariableTypeAnywhere(varName)
				
				callerType = self.getExprDataType(caller)
				
				#while callerType in self.compiler.defines:
				#	callerType = self.compiler.defines[callerType]
				
				callerClassName = extractClassName(callerType)
				memberName = node.childNodes[1].childNodes[0].nodeValue
				callerClass = self.getClass(callerClassName)
#				templateParams = self.getTemplateParams(removeUnmanaged(callerType), callerClassName, callerClass)
#				print("getExprDataTypeClean:")
#				print("Member: %s" % (memberName))
#				print("callerType: " + callerType)
#				print("callerClassName: " + callerClassName)
#				print("templateParams: " + str(templateParams))
#				callerClassImpl = callerClass.implementations["_".join(templateParams.values())]
#				print("Class implementations: " + str(callerClass.implementations))
#				callerClass.debugMembers()
#				print("Picking implementation '" + callerClassImpl.getParamString() + "'")
				callerClassImpl = self.getClassImplementationByTypeName(callerType)
				
				if memberName in callerClassImpl.members:
					#debug("Member '" + memberName + "' does exist")
					memberType = callerClassImpl.members[memberName].type
#					print(memberType)
#					print(callerType)
#					print(callerClassName)
#					print(self.currentTemplateParams)
#					print(templateParams)
#					print("-----")
					return self.currentClassImpl.translateTemplateName(memberType)
				else:
					pass
					#debug("Member '" + memberName + "' doesn't exist")
					
					# data access from a pointer
					#print(callerClassName, memberName)
					if callerClassName == "MemPointer" and memberName == "data":
						return callerType[callerType.find('<')+1:-1]
					
					memberFunc = "get" + capitalize(memberName)
					virtualGetCall = parseString("<call><function><access><value>%s</value><value>%s</value></access></function><parameters/></call>" % (node.childNodes[0].childNodes[0].toxml(), memberFunc)).documentElement
					
					return self.getCallDataType(virtualGetCall)
				
#				templatesUsed = (callerClassName != callerType)
#				
#				if templatesUsed:
#					templateParams = callerType[len(callerClassName) + 1: -1]
#					translateTemplateParams = callerClass.mapTemplateParams(templateParams)
#					
#					if memberType in translateTemplateParams:
#						return translateTemplateParams[memberType]
#					else:
#						return memberType
#				else:
#					return memberType
			elif node.tagName == "slice":
				#           slice.value       .range        .from/to
				sliceFrom = node.childNodes[1].childNodes[0].childNodes[0].firstChild.toxml()
				sliceTo =   node.childNodes[1].childNodes[0].childNodes[1].firstChild.toxml()
				memberFunc = "operatorSlice"
				virtualSliceCall = parseString("<call><function><access><value>%s</value><value>%s</value></access></function><parameters><parameter>%s</parameter><parameter>%s</parameter></parameters></call>" % (node.childNodes[0].childNodes[0].toxml(), memberFunc, sliceFrom, sliceTo)).documentElement
				
				return self.getCallDataType(virtualSliceCall)
			elif node.tagName == "not":
				return "Bool"
				#return self.getExprDataType(node.childNodes[0].childNodes[0])
			elif node.tagName == "unmanaged":
				self.inUnmanaged += 1
				expr = self.getExprDataTypeClean(node.childNodes[0].childNodes[0])
				self.inUnmanaged -= 1
				return "~" + expr
			elif node.tagName == "negative":
				return self.getExprDataTypeClean(node.childNodes[0].childNodes[0])
			elif len(node.childNodes) == 2: # Any binary operation
				op1 = node.childNodes[0].childNodes[0]
				op2 = node.childNodes[1].childNodes[0]
				#op1Type = self.getExprDataType(op1)
				#op2Type = self.getExprDataType(op2)
				
				# Recursive functions: Try to guess
				if self.inFunction and self.currentFunction:
					# Is the second operator the recursive call?
					if tagName(op2) == "call" and getElementByTagName(op2, "function").childNodes[0].nodeValue == self.currentFunction.getName():
						op1Type = self.getExprDataType(op1)
						self.currentFunctionImpl.returnTypes.append(op1Type)
						return getHeavierOperator(op1Type, self.currentFunctionImpl.getReturnType())
						#if self.currentFunctionImpl.returnTypes:
						#	return self.currentFunctionImpl.getReturnType()
						#else:
						#	return op1Type
					# Is the first operator the recursive call?
					elif tagName(op1) == "call" and getElementByTagName(op1, "function").childNodes[0].nodeValue == self.currentFunction.getName():
						op2Type = self.getExprDataType(op2)
						self.currentFunctionImpl.returnTypes.append(op2Type)
						return getHeavierOperator(op2Type, self.currentFunctionImpl.getReturnType())
						#if self.currentFunctionImpl.returnTypes:
						#	return self.currentFunctionImpl.getReturnType()
						#else:
						#	return self.getExprDataType(op2)
				
				op1Type = self.getExprDataType(op1)
				op2Type = self.getExprDataType(op2)
				
				#if op1Type == "UTF8String" and op2Type in nonPointerClasses:
				#	return "UTF8String"
				
				return self.getCombinationResult(node.tagName, op1Type, op2Type)
			
		raise CompilerException("Unknown data type for: " + node.toxml())
	
	def getFunctionCallInfo(self, node):
		funcNameNode = getFuncNameNode(node)
		
		caller = ""
		callerType = ""
		if isTextNode(funcNameNode): #and funcNameNode.tagName == "access":
			funcName = funcNameNode.nodeValue
		else:
			#print("XML: " + funcNameNode.childNodes[0].childNodes[0].toxml())
			callerType = self.getExprDataType(funcNameNode.childNodes[0].childNodes[0])
			caller = self.parseExpr(funcNameNode.childNodes[0].childNodes[0])
			funcName = funcNameNode.childNodes[1].childNodes[0].nodeValue
			#print(callerType + "::" + funcName)
		
		return caller, callerType, correctOperators(funcName)
	
	def getCombinationResult(self, operation, operatorType1, operatorType2):
		if operatorType1 in dataTypeWeights and operatorType2 in dataTypeWeights:
			if operation == "divide":
				dataType = getHeavierOperator(operatorType1, operatorType2)
				if dataType == "Double":
					return dataType
				else:
					return "Float"
			elif operation == "less" or operation == "greater" or operation == "less-or-equal" or operation == "greater-or-equal" or operation == "equal" or operation == "not-equal" or operation == "almost-equal" or operation == "and" or operation == "or":
				return "Bool"
			else:
				return getHeavierOperator(operatorType1, operatorType2)
		else:
			operatorType1 = removeUnmanaged(operatorType1)
			operatorType2 = removeUnmanaged(operatorType2)
			
			if operatorType1.startswith("MemPointer"):
				if operation == "index":
					return operatorType1[len("MemPointer<"):-1]
				if operatorType2.startswith("MemPointer"):
					if operation == "subtract":
						return "Size"
				if operation == "add" or operation == "subtract":
					return operatorType1
				return self.getCombinationResult(operation, "Size", operatorType2)
			if operatorType2.startswith("MemPointer"):
				return self.getCombinationResult(operation, operatorType1, "Size")
			
			# TODO: Remove temporary fix
			if operation == "index":
				if operatorType1.startswith("Array<"):
					return operatorType1[len("Array<"):-1]
				else:
					impl = self.implementFunction(operatorType1, "[]", [operatorType2])
					return impl.getReturnType()
			
			custom = self.implementFunction(operatorType1, correctOperators(operation), [operatorType2])
			if custom:
				return custom.getReturnType()
			
			raise CompilerException("Could not find an operator for the operation: " + operation + " " + operatorType1 + " " + operatorType2)
	
	def getVariableScopeAnywhere(self, name):
		scope = self.getVariableScope(name)
		if scope:
			return scope
		
		raise CompilerException("Unknown variable: %s" % name)
	
	def getVariableTypeAnywhere(self, name):
		var = self.getVariable(name)
		if var:
			#if var.type in self.currentTemplateParams:
			#	return self.currentTemplateParams[var.type]
			return var.type
		
		if name in self.currentClassImpl.members:
			return self.currentClassImpl.members[name].type
		
		if name in self.compiler.mainClassImpl.members:
			return self.compiler.mainClassImpl.members[name].type
		
		#print(self.getTopLevelScope().variables)
		if name in self.compiler.mainClass.classes:
			raise CompilerException("You forgot to create an instance of the class '" + name + "' by using brackets")
		elif name in self.compiler.mainClass.functions:
			raise CompilerException("A function call can only return a value if you use parentheses: '" + name + "()'")
		
		raise CompilerException("Unknown variable: " + name)
	
	def variableExistsAnywhere(self, name):
		if self.variableExists(name):
			return 1
		elif name in self.currentClassImpl.members:
			return 2
		elif name in self.compiler.mainClassImpl.members:
			return 3
		else:
			#print(name + " doesn't exist")
			return 0
	
	def classExists(self, className):
		if className == "":
			return True
		elif className in self.compiler.mainClass.classes:
			return True
		else:
			return False
	
	def isMemberAccessFromOutside(self, op1, op2):
		op1Type = self.getExprDataType(op1)
		op1ClassName = extractClassName(op1Type)
		#print(("get" + op2.nodeValue.capitalize()) + " -> " + str(self.compiler.classes[op1Type].functions.keys()))
		
		if not op1ClassName in self.compiler.mainClass.classes:
			return False
		
		accessingGetter = ("get" + capitalize(op2.nodeValue)) in self.getClass(op1ClassName).functions
		if isTextNode(op2) and (accessingGetter or (op2.nodeValue in self.getClassImplementationByTypeName(op1Type).members)):
			#print(self.currentFunction.getName() + " -> " + varGetter)
			#print(self.currentFunction.getName() == varGetter)
			
			if not (isTextNode(op1) and op1.nodeValue == "my"):
				# Make a virtual call
				return True
		
		return False
	
	def registerVariable(self, var):
		#var.name = self.getNamespacePrefix() + var.name
		debug("Registered variable '" + var.name + "' of type '" + var.type + "'")
		self.getCurrentScope().variables[var.name] = var
		#self.currentClassImpl.addMember(var)
	
	def handleUnmanaged(self, node):
		self.inUnmanaged += 1
		expr = self.parseExpr(node.childNodes[0])
		self.inUnmanaged -= 1
		return "~" + expr
	
	def handleParallel(self, node):
		codeNode = getElementByTagName(node, "code")
		
		joinAll = getMetaData(node, "wait-for-all-threads") != "false" #isMetaDataTrueByTag(node, "wait-for-all-threads")
		
		self.parallelBlockStack.append(list())
		self.inParallel += 1
		#self.pushScope()
		code = self.parseChilds(codeNode, "\t" * self.currentTabLevel, self.lineLimiter)
		#self.popScope()
		self.inParallel -= 1
		
		block = self.parallelBlockStack.pop()
		
		if joinAll:
			code += self.waitCustomThreadsCode(block)
		
		return code
	
	def handleShared(self, node):
		codeNode = getElementByTagName(node, "code")
		
		self.inShared += 1
		code = self.parseChilds(codeNode, "\t" * self.currentTabLevel, self.lineLimiter)
		self.inShared -= 1
		
		return code
	
	def handleNamespace(self, node):
		# TODO: Fully implement namespaces
		name = getElementByTagName(node, "name").firstChild.nodeValue
		
		#print("Namespace %s" % name)
		
		self.namespaceStack.append(name)
		if not name in self.currentClass.namespaces:
			print("Adding new namespace to '%s': '%s'" % (self.currentClass.name, name))
			self.currentClass.namespaces[name] = self.createNamespace(name)
		else:
			print("Namespace '%s' already exists!" % name)
		
		codeNode = getElementByTagName(node, "code")
		code = self.parseChilds(codeNode, "\t" * self.currentTabLevel, self.lineLimiter)
		
		self.namespaceStack.pop()
		
		return code
	
	def handleReturn(self, node):
		# THIS STEP MUST BE EXECUTED BEFORE expr = ... IS CALLED!
		# Recursive functions first need their data type value
		# THEN parseExpr -> implementFunction can be called
		retType = self.getExprDataType(node.childNodes[0])
		self.currentFunctionImpl.returnTypes.append(retType)
		
		# STEP 2
		expr = self.parseExpr(node.childNodes[0], False)
		
		if retType == "void":
			raise CompilerException("'%s' doesn't return a value" % nodeToBPC(node.childNodes[0]))
		
		#debug("Returning '%s' with type '%s' on current func '%s' with implementation '%s'" % (expr, retType, self.currentFunction.getName(), self.currentFunctionImpl.getName()))
		return self.returnSyntax % expr
	
	def handleParameters(self, pNode):
		pList = ""
		pTypes = []
		
		# For slicing:
		#<parameter>						= node
		#	<slice>							= node.firstChild
		#		<value>a</value>			= node.firstChild.firstChild
		#		<value>						= node.firstChild.childNodes[1]
		#			<range>					= node.firstChild.childNodes[1].firstChild
		#				<from>2</from>
		#				<to>3</to>
		#			</range>
		#		</value>
		#	</slice>
		#</parameter>
		
		for node in pNode.childNodes:
			paramType = self.getExprDataType(node.childNodes[0])
			
			# Typedefs
			paramType = self.prepareTypeName(paramType)
			
			#paramType = self.translateTemplateParam(paramType)
			pList += self.parseExpr(node.childNodes[0]) + ", "
			pTypes.append(paramType)
		
		return pList[:len(pList)-2], pTypes
	
	def getClass(self, className):
		if className == "":
			return self.compiler.mainClass
		elif className in self.compiler.specializedClasses:
			return self.compiler.specializedClasses[className]
		elif className in self.compiler.mainClass.classes:
			return self.compiler.mainClass.classes[className]
		else:
			raise CompilerException("Class '%s' has not been defined  [Error code 3]" % (className))
		
	def getClassImplementationByTypeName(self, typeName, initTypes = []):
		className = extractClassName(typeName)
		templateValues = extractTemplateValues(typeName)
		return self.getClass(className).requestImplementation(initTypes, splitParams(templateValues))
		
	def getParameterList(self, pNode):
		if pNode is None:
			return [], [], [], []
		
		pList = []
		pTypes = []
		pDefault = []
		pDefaultTypes = []
		
		for node in pNode.childNodes:
			name = ""
			type = ""
			defaultValue = ""
			defaultValueType = ""
			
			exprNode = node.childNodes[0]
			
			if isTextNode(exprNode):
				name = exprNode.nodeValue
			elif exprNode.tagName == "name":
				name = exprNode.childNodes[0].nodeValue
				defaultValue = self.parseExpr(node.childNodes[1].childNodes[0])
			elif exprNode.tagName == "access":
				name = "__" + exprNode.childNodes[1].childNodes[0].nodeValue
			elif exprNode.tagName == "assign":
				name = self.parseExpr(exprNode.childNodes[0].childNodes[0])
				defaultValue = self.parseExpr(exprNode.childNodes[1].childNodes[0])
				defaultValueType = self.getExprDataType(exprNode)
				
				# TODO: declare-type
				#type = defaultValueType
			elif exprNode.tagName == "declare-type":
				op1 = exprNode.childNodes[0].childNodes[0]
				if isElemNode(op1) and op1.tagName == "access":
					accessingObject = self.parseExpr(op1.childNodes[0].childNodes[0])
					accessingMember = self.parseExpr(op1.childNodes[1].childNodes[0])
					if accessingObject == self.myself:
						name = "__" + accessingMember
					else:
						raise CompilerException("'%s.%s' may not be used as a function parameter" % (accessingObject, accessingMember))
				else:
					name = self.parseExpr(op1)
				
				typeNode = exprNode.childNodes[1].childNodes[0]
				type = self.parseExpr(typeNode, True)
				
				# Typedefs
				type = self.prepareTypeName(type)
				
				#if typeNode.childNodes and isElemNode(typeNode) and typeNode.tagName == "unmanaged":
				#	type = "~" + type
			else:
				raise CompilerException("Invalid parameter %s" % (exprNode.toxml()))
			
			if name in replacedNodeValues:
				name = replacedNodeValues[name]
			
			pList.append(name)
			
			type = self.currentClassImpl.translateTemplateName(type)
			type = self.addMissingTemplateValues(type)
			
			type = self.prepareTypeName(type)
			
			# Use default value type if not set
			#if not type and defaultValueType:
			#	type = defaultValueType
			
			pTypes.append(type)
			pDefault.append(defaultValue)
			pDefaultTypes.append(defaultValueType)
		
		return pList, pTypes, pDefault, pDefaultTypes
	
	def parseChilds(self, parent, prefix = "", postfix = ""):
		lines = []
		for node in parent.childNodes:
			line = self.parseExpr(node)
			self.lastParsedNode.pop()
			
			if self.additionalCodePerLine:
				line = "%s%s%s%s" % ((postfix + prefix).join(self.additionalCodePerLine), postfix, prefix, line)
				self.additionalCodePerLine = []
				
			if line:
				lines.append(prefix)
				lines.append(line)
				lines.append(postfix)
		return ''.join(lines)
	
	def parseExpr(self, node, keepUnmanagedSign = True):
		# Set last node for debugging purposes
		self.lastParsedNode.append(node)
		
		if not keepUnmanagedSign:
			expr = self.parseExpr(node, True)
			# Remove unmanaged sign
			if len(expr) and expr[0] == "~":
				return expr[1:]
			return expr
		
		# Return text nodes directly (if it is not a string)
		if isTextNode(node):
			if node.nodeValue.startswith("bp_string_"):
				return self.id + "_" + node.nodeValue
			else:
				if node.nodeValue == "my":
					if self.useGC:
						return self.myself
					# TODO: Make sure the algorithm to find out whether 'self' is being used solely works 100%
					#opNode = node.parentNode.parentNode
					#numChildNodes = len(opNode.childNodes)
					#if numChildNodes > 1:
					#	return self.myself
					#else:
						# TODO: Unmanaged object initiations need to return 'this'
					#	return "shared_from_this()"
				#elif node.nodeValue == "null":
				#	return "NULL"
				# BigInt support
				elif node.nodeValue.isdigit():
					num = int(node.nodeValue)
					if num > INT32_MAX or num < INT32_MIN:
						return "(BigInt)(\"" + str(num) + "\")"
					else:
						return str(num)
				elif node.nodeValue == "true":
					return self.buildTrue()
				elif node.nodeValue == "false":
					return self.buildFalse()
				elif node.nodeValue in replacedNodeValues:
					nodeName = node.nodeValue
					nodeName = replacedNodeValues[node.nodeValue]
					return nodeName
				else:
					return node.nodeValue
				#else:
				#	return node.nodeValue
		
		tagName = node.tagName
		
		# Check which kind of tag it is
		if tagName == "value":
			return self.parseExpr(node.childNodes[0])
		elif tagName == "access":
			return self.handleAccess(node)
		elif tagName == "assign":
			return self.handleAssign(node)
		elif tagName == "call":
			return self.handleCall(node)
		elif tagName == "new":
			return self.handleNew(node)
		elif tagName == "if-block" or tagName == "try-block":
			return self.parseChilds(node, "", "")
		elif tagName == "else":
			return self.handleElse(node)
		elif tagName == "parameters":
			return self.parseChilds(node, "", ", ")[:-2]
		elif tagName == "parameter":
			if getElementByTagName(node, "default-value"):
				return self.parseExpr(node.childNodes[0].childNodes[0])
			return self.parseExpr(node.childNodes[0])
		elif tagName in enableOperatorOverloading:
			caller = self.parseExpr(node.childNodes[0].childNodes[0])
			callerType = self.getExprDataType(node.childNodes[0].childNodes[0])
			callerClassName = extractClassName(callerType)
			#valueType = self.getExprDataType(node.childNodes[1].childNodes[0])
			
			if callerClassName == "void":
				funcName = node.childNodes[0].childNodes[0].childNodes[0].childNodes[0].nodeValue
				raise CompilerException("Function '%s' has no return value" % funcName)
			
			if callerClassName in nonPointerClasses:
				pass#return "(%s+%s)" % (caller, op2)
			elif callerClassName == "MemPointer": #and isUnmanaged(callerType):
				pass#return "(%s + %s)" % (caller, op2)
			else:#if correctOperators(tagName) in self.getClassImplementationByTypeName(callerType).funcImplementations:
				memberFunc = correctOperators(tagName)
				if (not callerType in nonPointerClasses) and self.getClass(callerClassName).hasFunction(memberFunc):
					virtualIndexCall = parseString("<call><operator><access><value>%s</value><value>%s</value></access></operator><parameters><parameter>%s</parameter></parameters></call>" % (node.childNodes[0].childNodes[0].toxml(), memberFunc, node.childNodes[1].childNodes[0].toxml())).documentElement
					
					call = self.handleCall(virtualIndexCall)
					return call
				 
		#elif tagName == "not":
		#	return "!" + self.parseChilds(node)
		elif tagName == "index":
			caller = self.parseExpr(node.childNodes[0].childNodes[0])
			callerType = self.getExprDataType(node.childNodes[0].childNodes[0])
			index = self.parseExpr(node.childNodes[1].childNodes[0])
			callerClassName = extractClassName(callerType)
			
			if callerClassName == "MemPointer": #and isUnmanaged(callerType):
				return "%s[%s]" % (caller, index)
			
			memberFunc = "[]"
			virtualIndexCall = parseString("<call><operator><access><value>%s</value><value>%s</value></access></operator><parameters><parameter>%s</parameter></parameters></call>" % (node.childNodes[0].childNodes[0].toxml(), memberFunc, node.childNodes[1].childNodes[0].toxml())).documentElement
			
			return self.handleCall(virtualIndexCall)
		elif tagName == "class":
			return ""
		elif tagName == "function" or tagName == "operator" or tagName == "cast-definition":
			return ""
		elif tagName == "get" or tagName == "set":
			return ""
		elif tagName == "extern":
			return ""
		elif tagName == "operators":
			return ""
		elif tagName == "extern-function":
			return ""
		elif tagName == "template":
			return ""
		elif tagName == "require":
			return ""
		elif tagName == "ensure":
			return ""
		elif tagName == "test":
			return ""
		elif tagName == "define":
			return ""
		elif tagName == "not":
			return self.buildNegation(self.parseExpr(node.firstChild))
		elif tagName == "try":
			return self.handleTry(node)
		elif tagName == "catch":
			return self.handleCatch(node)
		elif tagName == "throw":
			return "throw %s" % self.parseExpr(node.firstChild)
		elif tagName == "namespace":
			return self.handleNamespace(node)
		elif tagName == "target":
			return self.handleTarget(node)
		elif tagName == "return":
			return self.handleReturn(node)
		elif tagName == "for":
			return self.handleFor(node)
		elif tagName == "flow-to":
			return self.handleFlowTo(node)
		elif tagName == "include":
			fileName = node.childNodes[0].nodeValue
			self.compiler.includes.append((self.dir + fileName)[len(self.compiler.modDir):]) #+= "#include \"" + node.childNodes[0].nodeValue + "\"\n"
			return ""
		elif tagName == "const":
			return self.handleConst(node)
		elif tagName == "break":
			return "break"
		elif tagName == "continue":
			return "continue"
		elif tagName == "parallel":
			return self.handleParallel(node)
		elif tagName == "shared":
			return self.handleShared(node)
		elif node.tagName == "template-call":
			return self.handleTemplateCall(node)
		elif node.tagName == "declare-type":
			
			if node.parentNode.tagName == "code":
				self.handleTypeDeclaration(node)
				return ""
			
			name = self.handleTypeDeclaration(node, insertTypeName = True)
			#print(name)
			return name
		elif node.tagName == "slice":
			#           slice.value       .range        .from/to
			sliceFrom = node.childNodes[1].childNodes[0].childNodes[0].firstChild.toxml()
			sliceTo =   node.childNodes[1].childNodes[0].childNodes[1].firstChild.toxml()
			memberFunc = "operatorSlice"
			virtualSliceCall = parseString("<call><function><access><value>%s</value><value>%s</value></access></function><parameters><parameter>%s</parameter><parameter>%s</parameter></parameters></call>" % (node.childNodes[0].childNodes[0].toxml(), memberFunc, sliceFrom, sliceTo)).documentElement
			
			return self.handleCall(virtualSliceCall)
		elif node.tagName == "unmanaged":
			return self.handleUnmanaged(node)
		elif node.tagName == "compiler-flags":
			return self.parseChilds(node, "", "")
		elif node.tagName == "compiler-flag":
			return self.handleCompilerFlag(node)
		elif tagName == "noop":
			return ""
		
		# Check parameterized blocks
		if tagName in self.paramBlocks:
			paramBlock = self.paramBlocks[node.tagName]
			keywordName = paramBlock[0]
			paramTagName = paramBlock[1]
			codeTagName = paramBlock[2]
			
			#if isElemNode(getElementByTagName(node, paramTagName)):
			#	print(getElementByTagName(node, paramTagName).childNodes[0].toprettyxml())
			
			condition = self.parseExpr(getElementByTagName(node, paramTagName).childNodes[0])
			
			self.pushScope()
			code = self.parseChilds(getElementByTagName(node, codeTagName), "\t" * self.currentTabLevel, self.lineLimiter)
			self.popScope()
			
			return self.buildParamBlock(keywordName, condition, code, "\t" * self.currentTabLevel)
		
		# Check operators
		for opLevel in self.compiler.parser.operatorLevels:
			for op in opLevel.operators:
				if tagName == op.name:
					if op.type == Operator.BINARY:
						if op.text == "\\":
							return self.parseBinaryOperator(node, " / ", True)
						return self.parseBinaryOperator(node, " " + op.text + " ", True)
					elif op.type == Operator.UNARY:
						return op.text + "(" + self.parseExpr(node.childNodes[0]) + ")"
		
		return ""
	
	def handleAccess(self, node):
		op1 = node.childNodes[0].childNodes[0]
		op2 = node.childNodes[1].childNodes[0]
		
		if op1.nodeType == Node.TEXT_NODE and op1.nodeValue in self.currentClass.namespaces:
			return op1.nodeValue + "_" + self.parseExpr(op2)
		
		callerType = self.getExprDataType(op1)
		callerClassName = extractClassName(callerType)
		
		if callerClassName in self.compiler.mainClass.classes:
			if callerClassName == "MemPointer" and isTextNode(op2):
				if op2.nodeValue == "data":
					return "(*%s)" % (self.parseExpr(op1))
			# TODO: Optimize
			# GET access
			isMemberAccess = self.isMemberAccessFromOutside(op1, op2)
			if isMemberAccess:
				#print("Replacing ACCESS with CALL: %s.%s" % (op1.toxml(), "get" + op2.nodeValue.capitalize()))
				#if isTextNode(op1) and op1.nodeValue == "my":
				#	op1xml = "this"
				#else:
				op1xml = op1.toxml()
				
				getFunc = parseString("<call><function><access><value>%s</value><value>%s</value></access></function><parameters/></call>" % (op1xml, "get" + capitalize(op2.nodeValue))).documentElement
				#print(getFunc.toprettyxml())
				return self.handleCall(getFunc)
		
		return self.parseBinaryOperator(node, self.ptrMemberAccessChar)
	
	def prepareTypeName(self, typeName):
		#print("PREPARE: " + typeName)
		while typeName in self.compiler.defines:
			typeName = self.compiler.defines[typeName]
		
		pos = typeName.find("<")
		if pos != -1:
			templateParts = []
			for param in splitParams(typeName[pos + 1:-1]):
				templateParts.append(self.prepareTypeName(param))
			
			typeName = typeName[:pos]
			templatePart = "<" + ", ".join(templateParts) + ">"
		else:
			templatePart = ""
		
		if typeName in self.compiler.specializedClasses:
			typeName = self.compiler.specializedClasses[typeName].name
		
		#print("PREPARED: " + typeName + templatePart)
		return typeName + templatePart
	
	def scanAhead(self, parent):
		for node in parent.childNodes:
			if isElemNode(node):
				if node.tagName == "class":
					self.scanClass(node)
				elif node.tagName == "function" or node.tagName == "operator":
					self.scanFunction(node)
				elif node.tagName == "getter":
					self.inGetter += 1
					result = self.scanFunction(node)
					self.inGetter -= 1
				elif node.tagName == "setter":
					self.inSetter += 1
					result = self.scanFunction(node)
					self.inSetter -= 1
				elif node.tagName == "cast-definition":
					self.inCastDefinition += 1
					result = self.scanFunction(node)
					self.inCastDefinition -= 1
				elif node.tagName == "extern":
					self.inExtern += 1
					self.scanAhead(node)
					self.inExtern -= 1
				elif node.tagName == "operators":
					self.inOperators += 1
					self.scanAhead(node)
					self.inOperators -= 1
				elif node.tagName == "casts":
					self.inCasts += 1
					self.scanAhead(node)
					self.inCasts -= 1
				elif node.tagName == "define":
					self.inDefine += 1
					self.scanAhead(node)
					self.inDefine -= 1
				elif node.tagName == "get" or node.tagName == "set":
					self.scanAhead(node)
				elif node.tagName == "template":
					self.inTemplate += 1
					self.scanTemplate(node)
					self.inTemplate -= 1
				elif node.tagName == "extends":
					self.inExtends += 1
					self.scanExtends(node)
					self.inExtends -= 1
				elif node.tagName == "extern-function":
					self.scanExternFunction(node)
				elif node.tagName == "assign" and self.inDefine > 0:
					self.scanDefine(node)
	
	def implementFunction(self, typeName, funcName, paramTypes):
		#if funcName == "init":
		#	print("%s.%s(%s)" % (typeName, funcName, ", ".join(paramTypes)))
			#classImpl = self.getClassImplementationByTypeName(typeName)
			#classImpl.initCallTypes = paramTypes
		funcName = correctOperators(funcName)
		
		# For casts
		#while funcName in self.compiler.defines:
		#	funcName = self.compiler.defines[funcName]
		
		key = typeName + "." + funcName + "(" + ", ".join(paramTypes) + ")"
		if key in self.compiler.funcImplCache:
			return self.compiler.funcImplCache[key]
		
		className = extractClassName(typeName)
		if className in nonPointerClasses:
			raise CompilerException("'%s' has not been defined (maybe another function returns the wrong value?)" % (key))
		
		#print(funcName, "|", className, "|", key)
		if not funcName in self.getClass(className).functions:
			classObj = self.getClass(className)
			tmpFunc = findFunctionInBaseClasses(classObj, funcName)
			
			if not tmpFunc:
				print(className + " contains the following functions:")
				print(" * " + "\n * ".join(self.getClass(className).functions.keys()))
				raise CompilerException("The '%s' function of class '%s' has not been defined" % (funcName, className))
		
		func = self.getClassImplementationByTypeName(typeName).getMatchingFunction(funcName, paramTypes)
		definedInFile = func.cppFile
		
		# Default parameters
		#paramTypesLen = len(paramTypes)
		#paramDefaultValueTypes = func.getParamDefaultValueTypes()
		#paramDefaultValueTypesLen = len(paramDefaultValueTypes)
		#if paramTypesLen < paramDefaultValueTypesLen:
		#	paramTypes += paramDefaultValueTypes[paramTypesLen:paramDefaultValueTypesLen]
		
		# Push
		oldFunc = definedInFile.currentFunction
		
		# Implement
		definedInFile.currentFunction = func
		funcImpl = definedInFile.implementLocalFunction(typeName, funcName, paramTypes)
		
		# Pop
		definedInFile.currentFunction = oldFunc
		
		if className == "":
			self.prototypesHeader += funcImpl.getPrototype()
		
		self.compiler.funcImplCache[key] = funcImpl
		return funcImpl
	
	def implementLocalFunction(self, typeName, funcName, paramTypes):
		className = extractClassName(typeName)
		
		# Save values
		oldGetter = self.inGetter
		oldSetter = self.inSetter
		oldOperator = self.inOperator
		oldCastDefinition = self.inCastDefinition
		oldImpl = self.currentClassImpl
		oldClass = self.currentClass
		oldFunction = self.currentFunction
		oldFunctionImpl = self.currentFunctionImpl
		self.inFunction += 1
		
		# Set new values
		self.currentClass = self.getClass(className)
		self.currentClassImpl = self.getClassImplementationByTypeName(typeName)
		
		node = self.currentFunction.node
		if node.tagName == "getter":
			self.inGetter += 1
		elif node.tagName == "setter":
			self.inSetter += 1
		elif node.tagName == "operator":
			self.inOperator += 1
		elif node.tagName == "cast-definition":
			self.inCastDefinition += 1
		
		if self.inCastDefinition:
			# For casts
			funcName = self.prepareTypeName(funcName)
		
		# Implement it
		funcImpl, codeExists = self.currentClassImpl.requestFuncImplementation(funcName, paramTypes)
		self.currentFunctionImpl = funcImpl
		
		if not codeExists:
			funcNode = funcImpl.func.node
			codeNode = getElementByTagName(funcNode, "code")
			
			#debug("Before:")
			#self.debugScopes()
			#debugPush()
			
			self.saveScopes()
			self.scopes = self.scopes[:1]
			
			self.pushScope()
			
			if typeName: #and not self.variableExistsAnywhere("my"):
				# TODO: removeUnmanaged(typeName) ? yes/no?
				self.registerVariable(self.createVariable("my", typeName, "", False, True, False))
			parameters, funcStartCode = self.getParameterDefinitions(getElementByTagName(funcNode, "parameters"), paramTypes, funcImpl.func.getParamDefaultValueTypes())
			
			#  * self.currentTabLevel
			oldTabLevel = self.currentTabLevel
			if typeName:
				self.currentTabLevel = 2
			else:
				self.currentTabLevel = 1
			
			funcImpl.setCode(funcStartCode + self.parseChilds(codeNode, "\t" * self.currentTabLevel, self.lineLimiter))
			
			self.currentTabLevel = oldTabLevel - 1
			
			self.restoreScopes()
			
			#debugPop()
			#debug("After:")
			#self.debugScopes()
		
		# Load previous values
		self.inFunction -= 1
		self.currentFunction = oldFunction
		self.currentFunctionImpl = oldFunctionImpl
		self.inGetter = oldGetter
		self.inSetter = oldSetter
		self.inOperator = oldOperator
		self.inCastDefinition = oldCastDefinition
		self.currentClass = oldClass
		self.currentClassImpl = oldImpl
		
		return funcImpl
	
	def addDefaultParameters(self, typeName, funcName, paramTypes, paramsString):
		func = self.getClassImplementationByTypeName(typeName).getMatchingFunction(funcName, paramTypes)
		#if not func:
		#	raise CompilerException("Couldn't")
		
		paramTypesLen = len(paramTypes)
		paramDefaultValues = func.getParamDefaultValues()
		paramDefaultValueTypes = func.getParamDefaultValueTypes()
		paramDefaultValuesLen = len(paramDefaultValues)
		if paramTypesLen < paramDefaultValuesLen:
			if paramsString:
				paramsString += ", "
			paramTypes += paramDefaultValueTypes[paramTypesLen:paramDefaultValuesLen]
			paramsString += ", ".join(paramDefaultValues[paramTypesLen:paramDefaultValuesLen])
			
		return paramTypes, paramsString
	
	def handleTarget(self, node):
		name = getElementByTagName(node, "name").childNodes[0].nodeValue
		if name == self.compiler.getTargetName() or matchesCurrentPlatform(name):
			return "\n" + self.parseChilds(getElementByTagName(node, "code"), "\t" * self.currentTabLevel, self.lineLimiter)
	
	def handleImport(self, node):
		importedModulePath = node.childNodes[0].nodeValue.strip()
		importedModule = getModulePath(importedModulePath, extractDir(self.file), self.compiler.getProjectDir(), ".bp")
		return self.buildModuleImport(importedModule)
	
	def handleElse(self, node):
		self.pushScope()
		code = self.parseChilds(getElementByTagName(node, "code"), "\t" * self.currentTabLevel, self.lineLimiter)
		self.popScope()
		
		return self.elseSyntax % (code, "\t" * self.currentTabLevel)
	
	def handleString(self, node):
		id = self.id + "_" + node.getAttribute("id")
		value = decodeCDATA(node.childNodes[0].nodeValue)
		
		# TODO: classExists(self.compiler.stringDataType)
		if self.stringClassDefined:
			dataType = self.compiler.stringDataType
			line = self.buildString(id, value)
		else:
			dataType = "CString"
			line = self.buildUndefinedString(id, value)
		
		var = self.createVariable(id, dataType, value, False, False, True)
		#self.currentClassImpl.addMember(var)
		self.getTopLevelScope().variables[id] = var
		self.compiler.stringCounter += 1
		return line
	
	def handleTemplateCall(self, node):
		op1 = self.parseExpr(node.childNodes[0].childNodes[0])
		op2 = self.parseExpr(node.childNodes[1].childNodes[0])
		
		# Template translation
		op1 = self.currentClassImpl.translateTemplateName(op1)
		op2 = self.currentClassImpl.translateTemplateName(op2)
		
		op2 = self.prepareTypeName(op2)
		
		return self.buildTemplateCall(op1, op2)
		
	def handleConst(self, node):
		self.inConst += 1
		code = self.parseChilds(node, "\t" * self.currentTabLevel, self.lineLimiter)
		self.inConst -= 1
		
		return code
	
	def handleTypeDeclaration(self, node, insertTypeName = True):
		self.inTypeDeclaration += 1
		typeName = self.parseExpr(node.childNodes[1], True)
		
		# Typedefs
		typeName = self.prepareTypeName(typeName)
		
		typeName = self.currentClassImpl.translateTemplateName(typeName)
		varName = self.parseExpr(node.childNodes[0])
		self.inTypeDeclaration -= 1
		
		if varName.startswith(self.memberAccessSyntax):
			memberName = varName[len(self.memberAccessSyntax):]
			self.currentClassImpl.addMember(self.createVariable(memberName, typeName, "", False, not extractClassName(typeName) in nonPointerClasses, False))
			return varName # ""
		
		variableExists = self.variableExistsAnywhere(varName)
		if variableExists:
			#["local", "global"][self.getVariableScopeAnywhere(varName) == self.getTopLevelScope()]
			for item in self.scopes:
				print(item.variables)
				print("===")
			raise CompilerException("'" + varName + "' has already been defined as a %s variable of the type '" % (["local", "class", "global"][variableExists - 1]) + self.getVariableTypeAnywhere(varName) + "'")
		else:
			#debug("Declaring '%s' as '%s'" % (varName, typeName))
			var = self.createVariable(varName, typeName, "", self.inConst, not typeName in nonPointerClasses, False)
			self.registerVariable(var)
			
			if insertTypeName:
				return self.buildTypeDeclaration(typeName, varName)
			else:
				return self.buildTypeDeclarationNameOnly(varName)
	
	def handleFlowTo(self, node):
		op1 = node.childNodes[0].childNodes[0]
		op2 = node.childNodes[0].childNodes[0]
		
		op1Expr = self.parseExpr(op1)
		op2Expr = self.parseExpr(op2)
		
		# TODO: Implement data flow
		return op1Expr
	
	def handleFor(self, node):
		fromNodeContent = getElementByTagName(node, "from").childNodes[0]
		toLimiterNode = getElementByTagName(node, "to")
		
		if toLimiterNode:
			toNodeContent = toLimiterNode.childNodes[0]
			operator = "<="
		else:
			toNodeContent = getElementByTagName(node, "until").childNodes[0]
			operator = "<"
		
		fromType = self.getExprDataType(fromNodeContent)
		
		iterExpr = self.parseExpr(getElementByTagName(node, "iterator").childNodes[0])
		fromExpr = self.parseExpr(fromNodeContent)
		toExpr = self.parseExpr(toNodeContent)
		toType = self.getExprDataType(toNodeContent)
		#stepExpr = self.parseExpr(getElementByTagName(node, "step").childNodes[0])
		
		self.pushScope()
		var = self.createVariable(iterExpr, getHeavierOperator(fromType, toType), fromExpr, False, False, False)
		typeInit = ""
		if not self.variableExistsAnywhere(iterExpr):
			self.getCurrentScope().variables[iterExpr] = var
			typeInit = var.type + " "
		code = self.parseChilds(getElementByTagName(node, "code"), "\t" * self.currentTabLevel, self.lineLimiter)
		self.popScope()
		
		varDefs = ""
		if not self.variableExistsAnywhere(toExpr):
			toVar = self.createVariable("bp_for_end_%s" % (self.compiler.forVarCounter), toType, "", False, not toType in nonPointerClasses, False)
			#self.getTopLevelScope().variables[toVar.name] = toVar
			self.varsHeader += self.buildVarDeclaration(toVar.type, toVar.name) + self.lineLimiter
			varDefs = "%s = %s;\n" % (toVar.name, toExpr)
			varDefs += "\t" * self.currentTabLevel
			toExpr = toVar.name
			self.compiler.forVarCounter += 1
		
		return self.buildForLoop(varDefs, typeInit, iterExpr, fromExpr, operator, toExpr, code, "\t" * self.currentTabLevel)
	
	def buildVarDeclaration(self, typeName, name):
		return self.buildSingleParameter(typeName, name)
	
	def addDivisionByZeroCheck(self, op):
		if isNumeric(op):
			if op != "0" and op != "0.0":
				return
			else:
				self.additionalCodePerLine.append(self.buildDivByZeroThrow(op))
				return
		
		self.additionalCodePerLine.append(self.buildDivByZeroCheck(op))
	
	def waitCustomThreadsCode(self, block):
		joinCodes = []
		tabs = "\t" * self.currentTabLevel
		for threadID in block:
			joinCodes.append(self.buildThreadJoin(threadID, tabs))
		return ''.join(joinCodes)
	
	def handleTry(self, node):
		codeNode = getElementByTagName(node, "code")
		
		self.pushScope()
		code = self.parseChilds(codeNode, "\t" * self.currentTabLevel, self.lineLimiter)
		self.popScope()
		
		return self.trySyntax % code
		
	def handleCatch(self, node):
		varNode = getElementByTagName(node, "variable")
		codeNode = getElementByTagName(node, "code")
		
		var = self.parseExpr(varNode)
		
		# Declare-type on exceptions
		if not var and varNode.firstChild and varNode.firstChild.nodeType != Node.TEXT_NODE and varNode.firstChild.tagName == "declare-type":
			varName = varNode.firstChild.childNodes[0].childNodes[0].nodeValue
			typeName = varNode.firstChild.childNodes[1].childNodes[0].nodeValue
			
			#print("Registering")
			#print(varName)
			#print(typeName)
			varObject = self.createVariable(varName, typeName, "", self.inConst, not typeName in nonPointerClasses, False)
			self.registerVariable(varObject)
			
			var = self.singleParameterSyntax % (self.adjustDataType(typeName), varName)
		
		if not var:
			var = "..."
		
		# Code needs to be compiled AFTER THE EXCEPTION VARIABLE HAS BEEN REGISTERED
		self.pushScope()
		code = self.parseChilds(codeNode, "\t" * self.currentTabLevel, self.lineLimiter)
		self.popScope()
		
		return self.catchSyntax % (var, code)
	
	def handleCall(self, node):
		caller, callerType, funcName = self.getFunctionCallInfo(node)
		
		# For casts
		funcName = self.prepareTypeName(funcName)
		
		params = getElementByTagName(node, "parameters")
		paramsString, paramTypes = self.handleParameters(params)
		
		debug(("--> [CALL] " + caller + "." + funcName + "(" + paramsString + ")").ljust(70) + " [my : " + callerType + "]")
		
		callerClassName = extractClassName(callerType)
		#if callerClassName == "void":
		#	raise CompilerException("Function '%s' has no return value" % getElementByTagName(node, "function"))
		callerClass = self.getClass(callerClassName)
		
		# MemPointer.free
		if funcName == "free" and callerClassName == "MemPointer":
			return self.buildDeleteMemPointer(caller)
		
		if not self.compiler.mainClass.hasExternFunction(funcName): #not funcName.startswith("bp_"):
			if not funcName in callerClass.functions:
				# Check extended classes
				func = findFunctionInBaseClasses(callerClass, funcName)
				
				if not func:
					if funcName[0].islower():
						raise CompilerException("Function '%s.%s' has not been defined [Error code 1]" % (callerType, funcName))
					else:
						raise CompilerException("Class '%s' has not been defined  [Error code 2]" % (funcName))
			else:
				func = callerClass.functions[funcName]
			
			# Optimized string concatenation
			if self.compiler.optimizeStringConcatenation:
				if funcName == "operatorAdd" and callerType == "UTF8String" and paramTypes[0] in {"UTF8String", "Int"}:
					# Check if above our node is an add node
					op = getElementByTagName(node, "operator")
					secondAddNode = op.firstChild.firstChild.firstChild
					
					if op and op.firstChild.tagName == "access" and tagName(secondAddNode) == "add":
						string1 = secondAddNode.childNodes[0].firstChild
						string2 = secondAddNode.childNodes[1].firstChild
						if string1 and string2:
							# Add one more parameter to the operator
							paramTypes = [self.getExprDataType(string2)] + paramTypes
							paramsString = "%s, %s" % (self.parseExpr(string2), paramsString)
							secondAddNode.parentNode.replaceChild(string1, secondAddNode)
							caller = self.parseExpr(string1)
							# Remove add node
							
						#print(("--> [CALL] " + caller + "." + funcName + "(" + paramsString + ")").ljust(70) + " [my : " + callerType + "]")
			
			# Default parameters
			paramTypes, paramsString = self.addDefaultParameters(callerType, funcName, paramTypes, paramsString)
			previousParamTypes = list(paramTypes)
			
			for i in range(len(paramTypes)):
				if paramTypes[i] == "void":
					raise CompilerException("'%s' does not return a value" % nodeToBPC(params.childNodes[i]))
			
			funcImpl = self.implementFunction(callerType, funcName, paramTypes)
			fullName = funcImpl.getName()
			
			# Casts
			for i in range(len(previousParamTypes)):
				pFrom = previousParamTypes[i]
				pTo = paramTypes[i]
				
				if pFrom != pTo and not canBeCastedTo(pFrom, pTo):
					# TODO: self.buildCall(caller, fullName, paramsString)
					debug("Type cast from '%s' to '%s'" % (pFrom, pTo))
					params = paramsString.split(",")
					params = params[:i] + [self.buildCall("(" + params[i] + ")", "to" + pTo, "")] + params[i + 1:]
					paramsString = ", ".join(params)
			
			# Check whether the given parameters match the default parameter types
			#defaultValueTypes = funcImpl.func.getParamDefaultValueTypes()
			#for i in range(len(defaultValueTypes)):
			#	if i >= paramTypesLen:
			#		break
			#	
			#	if defaultValueTypes[i] and paramTypes[i] != defaultValueTypes[i]:
			#		raise CompilerException("Call parameter types don't match the parameter default types of '%s'" % (funcName))
			
			# Parallel
			if self.inParallel >= 0 and node.parentNode and node.parentNode.parentNode and node.parentNode.parentNode.tagName == "parallel":
				threadID = self.compiler.customThreadsCount
				threadFuncID = fullName
				self.buildThreadFunc(threadFuncID, paramTypes)
				self.parallelBlockStack[-1].append(threadID)
				self.compiler.customThreadsCount += 1
				tabs = "\t" * self.currentTabLevel
				return self.buildThreadCreation(threadID, threadFuncID, paramTypes, paramsString, tabs)
				
			if (callerClass in nonPointerClasses) or isUnmanaged(callerType):
				return self.buildNonPointerCall(caller, fullName, paramsString)
			else:
				return self.buildCall(caller, fullName, paramsString)
		else:
			return self.externCallSyntax % (funcName, paramsString)
	
	def pushScope(self):
		self.currentTabLevel += 1
		ScopeController.pushScope(self)
		
	def popScope(self):
		self.currentTabLevel -= 1
		ScopeController.popScope(self)
	
	def debugScopes(self):
		counter = 0
		for scope in self.scopes:
			debug("[" + str(counter) + "]")
			for name, variable in scope.variables.items():
				debug(" => " + variable.name.ljust(40) + " : " + variable.type)
			counter += 1
	
	def implementCasts(self):
		# Implement casts BEFORE class functions are written
		for classObj in self.localClasses:
			if not classObj.isExtern:
				for classImplId, classImpl in classObj.implementations.items():
					for funcList in classObj.functions.values():
						if funcList:
							func = funcList[0]
							if func.isCast:
								#print("===> " + classImpl.getName() + "." + func.getName())
								self.implementFunction(classImpl.getName(), func.getName(), [])
	
	def writeFunctions(self):
		for func in self.localFunctions:
			for funcImpl in func.implementations.values():
				self.functionsHeader += "%s\n" % (funcImpl.getFullCode())
	
	def getRootNode(self):
		return self.root
		
	def getCodeNode(self):
		return self.codeNode
		
	def getHeaderNode(self):
		return self.headerNode
		
	def getDependenciesNode(self):
		return self.dependencies
	
	def getFilePath(self):
		return self.file
	
	def getFileName(self):
		return self.file[len(self.dir):]
	
	def getDirectory(self):
		return self.dir
	
	def getCode(self):
		return NotImplementedError()
