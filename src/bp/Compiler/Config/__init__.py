from bp.Compiler.Utils import *

# Configuration
buildAndExecute = 1
buildGraphViz = 0

def getModuleDir():
	return "../../../"#"../../"

def getModulePath(importedModule, fileDir, projectDir, extension = ".bp"):
	# ########################### #
	# Priority for module search: #
	# ########################### # ############# #
	# 1. Local    # 4. Project    # 7. Global     #
	# ########################### ############### #
	# 2. File     # 5.  File      # 8.  File      #
	# 3. Dir      # 6.  Dir       # 9.  Dir       #
	# ########################### # ############# #
	fileDir = fixPath(fileDir)
	projectDir = fixPath(projectDir)
	
	importedModulePath = importedModule.replace(".", "/")
	
	# Local
	importedFile = fileDir + importedModulePath + extension
	
	importedInFolder = fileDir + importedModulePath
	importedInFolder += "/" + stripAll(importedInFolder) + extension
	
	# Project
	pImportedFile = projectDir + importedModulePath + extension
	
	pImportedInFolder = projectDir + importedModulePath
	pImportedInFolder += "/" + stripAll(pImportedInFolder) + extension
	
	# Global
	gImportedFile = getModuleDir() + importedModulePath + extension
	
	gImportedInFolder = getModuleDir() + importedModulePath
	gImportedInFolder += "/" + stripAll(pImportedInFolder) + extension
	
	# Debug
	#print(importedFile, importedInFolder, pImportedFile, pImportedInFolder, gImportedFile, gImportedInFolder)
	
	# TODO: Implement global variant
	
	if os.path.isfile(importedFile):
		return os.path.abspath(importedFile)
	elif os.path.isfile(importedInFolder):
		return os.path.abspath(importedInFolder)
	elif os.path.isfile(pImportedFile):
		return os.path.abspath(pImportedFile)
	elif os.path.isfile(pImportedInFolder):
		return os.path.abspath(pImportedInFolder)
	elif os.path.isfile(gImportedFile):
		return os.path.abspath(gImportedFile)
	elif os.path.isfile(gImportedInFolder):
		return os.path.abspath(gImportedInFolder)
	
	return ""