from PyQt4 import QtGui, QtCore

class BPMessageView(QtGui.QListWidget):
	
	def __init__(self, parent):
		super().__init__(parent)
		self.bpIDE = parent
		self.setWordWrap(True)
		
		self.lastLineNumber = -2
		self.lastErrorMessage = ""
		self.lastErrorFilePath = ""
		
		#self.setContentsMargins(0, 0, 0, 0)
		#self.setMaximumHeight(0)
		#self.setScrollBarPolicy(QtGui.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
		self.icon = QtGui.QIcon("images/icons/status/dialog-warning.png")
		self.itemClicked.connect(self.goToLineOfItem)
		
	def goToLineOfItem(self, item):
		errorFilePath = item.data(QtCore.Qt.UserRole + 1)
		lineNum = int(item.data(QtCore.Qt.UserRole + 2))
		
		if errorFilePath != self.bpIDE.getFilePath():
			self.bpIDE.openFile(errorFilePath)
		
		if lineNum != -1:
			self.bpIDE.goToLineEnd(lineNum)
		
	def addMessage(self, msg):
		newItem = QtGui.QListWidgetItem(self.icon, msg)
		newItem.setStatusTip(str(-1))
		self.addItem(newItem)
		
	def addLineBasedMessage(self, errorFilePath, lineNumber, msg):
		newItem = QtGui.QListWidgetItem(self.icon, msg)
		
		newItem.setData(QtCore.Qt.UserRole + 1, errorFilePath)
		newItem.setData(QtCore.Qt.UserRole + 2, lineNumber)
		
		info = "<strong>%s</strong><br/>Line [%d]: %s" % (errorFilePath, lineNumber, msg)
		newItem.setToolTip(info)
		#self.setSizeHint(QtCore.QSize(0, 10))
		self.addItem(newItem)
		
	def updateViewParser(self):
		# Last parser exception
		ce = self.bpIDE.codeEdit
		
		if ce and ce.updater and ce.updater.lastException:
			e = ce.updater.lastException
			ce.updater.lastException = None
			lineNumber = e.getLineNumber()
			errorMessage = e.getMsg()
			errorFilePath = e.getFilePath()
			
			if lineNumber != self.lastLineNumber or errorMessage != self.lastErrorMessage or errorFilePath != self.lastErrorFilePath:
				self.clear()
				self.addLineBasedMessage(errorFilePath, lineNumber, errorMessage)
				self.lastLineNumber = lineNumber
				self.lastErrorMessage = errorMessage
				self.lastErrorFilePath = errorFilePath
		else:
			self.lastLineNumber = -2
			self.lastErrorMessage = ""
			self.lastErrorFilePath = ""
			self.clear()
		
	def updateViewPostProcessor(self):
		# Last post processor exception
		pp = self.bpIDE.postProcessorThread
		if pp and pp.lastException:
			e = pp.lastException
			pp.lastException = None
			errorMessage = e.getMsg()
			self.addMessage(errorMessage)
		
	def updateView(self):
		if self.bpIDE.intelliEnabled:
			itemNum = self.count()
			if itemNum:
				#self.adjustSize()#resize(0, 0)
				#self.setMaximumHeight(self.count() * 50)
				
				maxHeight = 13
				for i in range(itemNum):
					maxHeight += self.visualItemRect(self.item(i)).height() + 2
				self.setMaximumHeight(maxHeight)
				
				if self.isHidden():
					self.show()
			else:
				if self.isVisible():
					self.hide()
