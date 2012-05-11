from bp.Tools.IDE.Editor import *

class BPWorkspace(QtGui.QTabWidget):
	
	def __init__(self, bpIDE, wsID):
		parent = bpIDE.workspacesContainer
		super().__init__(parent)
		
		self.bpIDE = bpIDE
		self.wsID = wsID
		self.filesClosed = []
		
		if bpIDE.config.documentModeEnabled:
			self.setDocumentMode(True)
		else:
			self.setDocumentMode(False)
		
		self.setTabsClosable(True)
		self.setMovable(True)
		#self.setTabShape(QtGui.QTabWidget.Triangular)
		self.hide()
		
		self.currentChanged.connect(self.changeCodeEdit)
		self.tabCloseRequested.connect(self.closeCodeEdit)
		parent.layout().addWidget(self)
		
	def addAndSelectTab(self, widget, name):
		index = self.addTab(widget, name)
		self.setCurrentIndex(index)
		
		# Buttons widget in the status bar
		self.bpIDE.workspacesView.updateCurrentWorkspace()
		
	def getWorkspaceID(self):
		return self.wsID
		
	def getTabNameList(self):
		tabNames = []
		for i in range(self.count()):
			tabNames.append(self.tabText(i))
		return tabNames
		
	def getCodeEditList(self):
		ceList = []
		tabCount = self.count()
		for i in range(tabCount):
			ceList.append(self.widget(i))
		return ceList
		
	def changeCodeEdit(self, index):
		#print("CODE EDIT CHANGED TO INDEX %d" % index)
		if index != -1:
			self.bpIDE.codeEdit = self.widget(index)
			self.bpIDE.codeEdit.setFocus()
			self.bpIDE.codeEdit.setCompleter(self.bpIDE.completer)
			self.bpIDE.codeEdit.runUpdater()
			
			if self.currentIndex() != index:
				self.setCurrentIndex(index)
		
		if self.bpIDE.viewsInitialized:
			self.bpIDE.dependencyView.clear()
			self.bpIDE.msgView.clear()
			self.bpIDE.xmlView.clear()
		
		self.bpIDE.updateLineInfo()
		
		if self.count():
			self.show()
		else:
			self.hide()
			
	def getCodeEditByPath(self, path):
		for i in range(self.count()):
			ce = self.widget(i)
			if ce.getFilePath() == path:
				return i, ce
		
		return -1, None
		
	def closeCodeEdit(self, index):
		if self.widget(index) == self.bpIDE.codeEdit and self.bpIDE.codeEdit is not None:
			path = self.bpIDE.getFilePath()
			if path and not self.bpIDE.isTmpPath(path):
				self.filesClosed.append(path)
		
		self.removeTab(index)
		
		# Update codeEdit
		#self.changeCodeEdit(self.currentIndex())
		#self.bpIDE.codeEdit = self.widget(self.currentWidget())
		#self.bpIDE.codeEdit.setFocus()
		
		# Update is not needed
		# self.removeTab automatically fires the signal
		# that the index has changed.
		
		# Buttons widget in the status bar
		self.bpIDE.workspacesView.updateCurrentWorkspace()
		
	def closeCurrentCodeEdit(self):
		self.closeCodeEdit(self.currentIndex())
		
	def updateCurrentCodeEditName(self):
		if self.count():
			self.setTabText(self.currentIndex(), stripAll(self.currentWidget().getFilePath()))
		
	def activateWorkspace(self):
		#self.tabWidget.show()
		self.changeCodeEdit(self.currentIndex())#bpIDE.codeEdit = self.currentWidget()
		
	def deactivateWorkspace(self):
		#self.tabWidget.show()
		self.bpIDE.codeEdit = None
		self.hide()
		#for workspace in self.bpIDE.workspaces:
		#	workspace.hide()