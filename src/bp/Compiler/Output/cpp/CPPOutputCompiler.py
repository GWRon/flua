####################################################################
# Header
####################################################################
# Target:   C++ Code
# Author:   Eduard Urbach

####################################################################
# License
####################################################################
# (C) 2011  Eduard Urbach
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
from bp.Compiler.Output.cpp.CPPOutputFile import *
from bp.Compiler.Utils import *
from bp.Compiler.Config import *
import codecs
import subprocess
import os
import sys

####################################################################
# Classes
####################################################################
class CPPOutputCompiler(Benchmarkable):
	
	def __init__(self, inpCompiler = None):
		
		if inpCompiler:
			self.inputCompiler = inpCompiler
			self.inputFiles = inpCompiler.getCompiledFiles()
			self.projectDir = self.inputCompiler.getProjectDir()
		else:
			self.projectDir = ""
		
		self.compiledFiles = dict()
		self.compiledFilesList = []
		self.modDir = getModuleDir()
		self.bpRoot = fixPath(os.path.abspath(self.modDir + "../"))
		self.libsDir = fixPath(os.path.abspath(self.modDir + "../libs/cpp/"))
		self.stringCounter = 0
		self.fileCounter = 0
		self.forVarCounter = 0
		self.outputDir = ""
		self.mainFile = None
		self.mainCppFile = ""
		self.customCompilerFlags = []
		self.funcImplCache = {}
		self.includes = []
		self.stringDataType = "~UTF8String"
		self.needToInitStringClass = False
		
		self.mainClass = CPPClass("")
		self.mainClassImpl = self.mainClass.requestImplementation([], [])
		
		if os.name == "nt":
			self.staticStdcppLinking = True
		else:
			self.staticStdcppLinking = False
		
		self.gmpEnabled = False
		
		# Expression parser
		self.initExprParser()
		
	def initExprParser(self):
		self.parser = getBPCExpressionParser()
		
	def getProjectDir(self):
		return self.projectDir
		
	def compile(self, inpFile):
		cppOut = CPPOutputFile(self, inpFile.getFilePath(), inpFile.getRoot())
		
		if len(self.compiledFiles) == 0:
			self.mainFile = cppOut
			self.projectDir = extractDir(self.mainFile.getFilePath())
		
		# This needs to be executed BEFORE the imported files have been compiled
		# It'll prevent a file from being processed twice
		self.compiledFiles[inpFile] = cppOut
		
		# Compile imported files first
		for imp in inpFile.getImportedFiles():
			inFile = self.inputCompiler.getFileInstanceByPath(imp)
			if (not inFile in self.compiledFiles):
				self.compile(inFile)
		
		# This needs to be executed AFTER the imported files have been compiled
		# It'll make sure the files are called in the correct (recursive) order
		self.compiledFilesList.append(cppOut)
		
		# After the dependencies have been compiled, compile itself
		try:
			cppOut.compile()
		except CompilerException as e:
			raise OutputCompilerException(e.getMsg(), cppOut)
		
		# Change string class
		#if self.mainClass.hasClassByName("UTF8String"):
		#	self.stringDataType = "~UTF8String"
	
	def writeToFS(self):
		#dirOut = fixPath(os.path.abspath(dirOut))
		#self.outputDir = dirOut
		cppFiles = self.compiledFiles.values()
		
		# Implement all casts
		for cppFile in cppFiles:
			cppFile.implementCasts()
		
		# Write to files
		for cppFile in cppFiles:
			#fileOut = dirOut + stripExt(os.path.relpath(cppFile.file, self.projectDir)) + "-out.hpp"
			fileOut = stripExt(cppFile.file) + "-out.hpp"
			
			# Directory structure
			concreteDirOut = os.path.dirname(fileOut)
			if not os.path.isdir(concreteDirOut):
				os.makedirs(concreteDirOut)
			
			with codecs.open(fileOut, "w", encoding="utf-8") as outStream:
				outStream.write(cppFile.getCode())
			
			# Write CPP main file (main-out.cpp)
			if cppFile.isMainFile:
				hppFile = os.path.basename(fileOut)
				
				#fileOut = stripExt(cppFile.file[len(self.projectDir):]) + "-out.cpp"
				fileOut = stripExt(cppFile.file) + "-out.cpp"
				self.mainCppFile = fileOut
				
				# Write main file
				with open(fileOut, "w") as outStream:
					outStream.write("#include <bp_decls.hpp>\n#include \"" + hppFile + "\"\n\nint main(int argc, char *argv[]) {\n" + self.getFileExecList() + "\treturn 0;\n}\n")
		
		# Decls file
		self.outputDir = extractDir(os.path.abspath(self.mainCppFile))
		fileOut = self.outputDir + "bp_decls.hpp"
		with open(fileOut, "w") as outStream:
			outStream.write("#ifndef " + "bp__decls__hpp" + "\n#define " + "bp__decls__hpp" + "\n\n")
			
			# Basic data types
			outStream.write("#include <cstdint>\n")
			outStream.write("#include <cstdlib>\n")
			if self.gmpEnabled:
				outStream.write("#include <gmp/gmpxx.h>\n")
			for dataType, definition in dataTypeDefinitions.items():
				outStream.write("typedef %s %s;\n" % (definition, dataType))
			outStream.write("typedef %s %s;\n" % ("CString", "String"))
			outStream.write("#define %s %s\n" % ("Ptr", "boost::shared_ptr"))
			outStream.write("\n")
			
			# Classes
			for className, classObj in self.mainClass.classes.items():
				if classObj.templateNames:
					outStream.write("template <typename %s> " % (", typename ".join(classObj.templateNames)))
				outStream.write("class BP%s;\n" % (className))
			
			#for implName, impl in self.mainClass.implementations[""].funcImplementations:
			#	outStream.write("// func %s;\n" % (implName))
			
			# Extern functions
			for externFunc in self.mainClass.externFunctions:
				outStream.write("// extern func %s;\n" % (externFunc))
			
			# Includes
			for incl in self.includes:
				outStream.write("#include <%s>\n" % (incl))
			
			outStream.write("\n#endif\n")
	
	def build(self, fhOut = sys.stdout.write, fhErr = sys.stderr.write):
		exe = stripExt(self.mainCppFile)
		if os.path.isfile(exe):
			os.unlink(exe)
		
		compilerName = "g++"
		
		compilerPath = getGCCCompilerPath()
		currentPath = os.path.abspath("./")
		
		if os.name == "nt":
			os.chdir(compilerPath)
		
		# Compiler
		ccCmd = [
			compilerName,
			"-c",
			fixPath(self.mainCppFile),
			"-o%s" % fixPath(exe + ".o"),
			"-I" + fixPath(self.outputDir),
			"-I" + fixPath(self.modDir),
			"-I" + fixPath(self.bpRoot + "include/cpp/"),
			#"-L" + self.libsDir,
			"-std=c++0x",
			"-Wall",
			#"-pipe",
			#"-frerun-cse-after-loop",
			#"-frerun-loop-opt",
			#"-ffast-math",
			#"-O3",
			#"-march=native",
			#"-mtune=native",
		]
		
		additionalLibs = []
		if self.gmpEnabled:
			additionalLibs += [
				"-lgmpxx",
				"-lgmp",
			]
		
		if self.staticStdcppLinking:
			staticRuntime = [
				"-static-libgcc",
				"-static-libstdc++",
			]
		else:
			# Dynamic linking seems to be faster on Linux
			staticRuntime = []
		
		# Linker
		linkCmd = [
			compilerName,
			"-o%s" % fixPath(exe),
			fixPath(exe + ".o"),
			"-L" + fixPath(self.libsDir),
			#"-ltheron",
			#"-lboost_thread",
			#"-lpthread"
		] + staticRuntime + additionalLibs + self.customCompilerFlags
		
		try:
			self.startBenchmark()
			print("\nStarting compiler:")
			print(" \\\n ".join(ccCmd))
			
			startProcess(ccCmd, fhOut, fhErr)
			
			self.endBenchmark()
			
			self.startBenchmark()
			print("\nStarting linker:")
			print("\n ".join(linkCmd))
			
			startProcess(linkCmd, fhOut, fhErr)
			
			self.endBenchmark()
		except OSError:
			print("Couldn't start " + compilerName)
		finally:
			if os.name == "nt":
				os.chdir(currentPath)
		
		return exe
	
	def execute(self, exe, fhOut = sys.stdout.write, fhErr = sys.stderr.write):
		cmd = [exe]
		
		try:
			startProcess(cmd, fhOut, fhErr)
		except OSError:
			print("Can't execute '%s'" % exe)
	
	def getFileExecList(self):
		files = ""
		for cppFile in self.compiledFilesList:
			files += "\texec_" + cppFile.id + "();\n"
		return files
	
	def getTargetName(self):
		return "C++"
