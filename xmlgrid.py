import sublime, sublime_plugin
import xml.etree.ElementTree as etree
from io import StringIO

def findMultipleChildren(element):
	"""find the first element in document order that contains multiple children."""
	children = list(element)
	if len(children) > 1:
		return children
	for item in children:
		check = findMultipleChildren(item)
		if check is not None:
			return check
	return None

def hierarchyToHeading(hierarchy):
	"""convert the given hierarchy to a column heading."""
	heading = ''
	for item in hierarchy:
		if item.startswith('@'):
			item = '[' + item + ']'
		elif heading != '':
			heading += '/'
		heading += item
	return heading

def recordValue(headings, values, hierarchy, heading, value):
	"""store the given heading and value."""
	if value is None:
		value = ''
	hierarchy = hierarchy[:]
	if heading is not None:
		hierarchy.append(heading)
	hierarchy = tuple(hierarchy)
	if hierarchy not in headings:
		headings.append(hierarchy)
	values[hierarchy] = value

def addAllChildrenToDictionary(element, headings, values, hierarchy, includeAttributes):
	"""recursively parse the xml element and store found headings and values."""
	if includeAttributes:
		for attr in element.items():
			recordValue(headings, values, hierarchy, '@' + attr[0], attr[1])
	
	children = list(element)
	if len(children) > 0:
		for child in children:
			hierarchy.append(child.tag)
			addAllChildrenToDictionary(child, headings, values, hierarchy, includeAttributes)
			hierarchy.pop()
	else:
		recordValue(headings, values, hierarchy, None, element.text)

def isSGML(view):
	"""return True if the view's syntax is XML."""
	currentSyntax = view.settings().get('syntax')
	if currentSyntax is not None:
		XMLSyntax = 'Packages/XML/'
		return currentSyntax.startswith(XMLSyntax)
	else:
		return False

def findNamespacePrefix(hierarchy, findNamespaceURI):
	"""given a hierarchy of namespace URIs and prefixes, find the given URI and return it's prefix followed by a colon."""
	for namespaces in hierarchy:
		for namespace in namespaces:
			if namespace[1] == findNamespaceURI:
				prefix = namespace[0]
				if prefix is None or prefix == '':
					prefix = ''
				else:
					prefix += ':'
				return prefix
	return ''


def extractNamespaceURI(qualifiedName):
	"""given an ElementTree fully qualified tag or attribute name and extract the namespace URI and the local name separately."""
	nsStart = qualifiedName.find('{')
	nsEnd = qualifiedName.find('}')
	if nsStart > -1:
		namespaceURI = qualifiedName[nsStart + 1:nsEnd]
		local = qualifiedName[0:nsStart] + qualifiedName[nsEnd + 1:]
	else:
		local = qualifiedName
		namespaceURI = None
	return (namespaceURI, local)

def parseXMLFile(fileRef, includeXMLNSAttributes):
	"""parse the given xml file reference into a DOM, converting ElementTree's namespace URIs in the tag name to the prefix."""
	root = None
	nextNamespaces = []
	hierarchy = []
	for event, item in etree.iterparse(fileRef, ('start', 'start-ns', 'end')):
		if event == 'start-ns':
			nextNamespaces.append(item)
		elif event == 'start':
			if root is None:
				root = item
			hierarchy.append(nextNamespaces)
			
			namespaceURI, local = extractNamespaceURI(item.tag)
			prefix = findNamespacePrefix(hierarchy, namespaceURI)
			item.tag = prefix + local
			
			# recreate attributes dictionary
			attributes = {}
			if includeXMLNSAttributes:
				# add xmlns attributes back in, as ElementTree removes them
				for namespaces in nextNamespaces:
					prefix = namespaces[0]
					if prefix != '':
						prefix = ':' + prefix
					attributes['xmlns' + prefix] = namespaces[1]
			
			for attribute in item.attrib:
				namespaceURI, local = extractNamespaceURI(attribute)
				prefix = findNamespacePrefix(hierarchy, namespaceURI)
				attributes[prefix + local] = item.attrib[attribute]
			
			item.attrib = attributes
			
			if len(nextNamespaces) > 0:
				nextNamespaces = []
		elif event == 'end':
			hierarchy.pop()
	return root

def getCSVValue(value, separator):
	if value is None:
		value = ''
	quote = '"'
	# the following text qualification rules and quote doubling are based on recommendations in RFC 4180
	if quote in value or value.endswith(' ') or value.endswith('\t') or value.startswith(' ') or value.startswith('\t') or '\n' in value or separator in value: # qualify the text in quotes if it contains a quote, starts or ends in whitespace, or contains the separator or a newline
		value = quote + value.replace(quote, quote + quote) + quote # to escape a quote, we double it up
	return value

class XmlToGridCommand(sublime_plugin.TextCommand): #sublime.active_window().active_view().run_command('xml_to_grid')
	def run(self, edit):
		sublime.status_message('parsing xml...')
		# parse the view as xml
		xmlString = self.view.substr(sublime.Region(0, self.view.size()))
		
		root = parseXMLFile(StringIO(xmlString), False)
		
		sublime.status_message('converting xml to grid...')
		# find the elements that will become rows in the grid
		children = findMultipleChildren(root)
		
		# read the settings
		settings = sublime.load_settings('xmlgrid.sublime-settings')
		includeAttributes = settings.get('include_attributes', True)
		separator = settings.get('field_separator', ' ')
		
		# parse the xml and get all headings and values
		rows = []
		headings = []
		for child in children:
			row = {}
			addAllChildrenToDictionary(child, headings, row, [child.tag], includeAttributes)
			rows.append(row)
		
		# create a new view to write the grid to
		gridView = self.view.window().new_file()
		
		# if grid-mode
		if separator == ' ':
			linesForCell = lambda heading, row: row.get(heading, '').split('\n')
			# determine the contents of each cell in the grid
			columns = list(map(lambda heading: [[hierarchyToHeading(heading)]] + list(map(lambda row: linesForCell(heading, row), rows)), headings))
			
			# determine the size of each row
			rowSizes = []
			for column in columns:
				for rowNumber in range(len(column)):
					if len(rowSizes) <= rowNumber:
						rowSizes.append(0)
					rowSizes[rowNumber] = max(len(column[rowNumber]), rowSizes[rowNumber])
			
			# if some cells span multiple lines
			if max(rowSizes) > 1:
				# insert line numbers
				rowNumbers = [['#']]
				for rowNumber in range(len(rowSizes)):
					rowNumbers.append([str(rowNumber + 1)])
				
				columns[:0] = [rowNumbers]
			
			# determine the size of each column
			colSizes = list(map(lambda column: max(map(lambda cell: max(list(map(lambda line: len(line), cell))), column)) + 1, columns)) # the + 1 is to ensure that there is a gap between fields
			
			# determine column start positions
			index = 0
			colStarts = []
			for colsize in colSizes:
			 	colStarts.append(index)
			 	index += colsize
			
			# write empty spaces for all lines first, they will be replaced later
			for rowSize in rowSizes:
				for rowNumber in range(rowSize):
					gridView.insert(edit, gridView.size(), (' ' * index) + '\n')
			index += 1 # account for the new line character at the end of each line
			
			# write the cells
			
			getPoint = lambda columnNumber, rowNumber: (rowNumber * index) + colStarts[columnNumber]
			
			for columnNumber in range(len(headings)): # for each column
				currentRow = 0
				for rowNumber in range(len(rowSizes)): # for each row
					rowStart = currentRow
					linesForCell = columns[columnNumber][rowNumber]
					for rowLine in linesForCell:
						point = getPoint(columnNumber, currentRow)
						gridView.replace(edit, sublime.Region(point, point + len(rowLine)), rowLine)
						currentRow += 1
					currentRow = rowStart + rowSizes[rowNumber]
		# if csv-mode
		else:
			# write the headings
			gridView.insert(edit, gridView.size(), separator.join(map(hierarchyToHeading, headings)) + '\n')
			
			# write the rows
			for row in rows:
				gridView.insert(edit, gridView.size(), separator.join(map(lambda heading: getCSVValue(row.get(heading, ''), separator), headings)) + '\n')
		
		sublime.status_message('')
	def is_enabled(self):
		return isSGML(self.view)
	def is_visible(self):
		return isSGML(self.view)
	
