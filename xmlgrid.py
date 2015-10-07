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
	return view.score_selector(0, 'text.xml') > 0

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
		includeGridLines = settings.get('include_gridlines', True)
		alwaysIncludeLineNumbers = settings.get('always_include_line_numbers', False)
		
		# parse the xml and get all headings and values
		rows = []
		headings = []
		for child in children:
			row = {}
			addAllChildrenToDictionary(child, headings, row, [child.tag], includeAttributes)
			rows.append(row)
		# prepend a heading row now that we have all the headings
		row = {}
		for heading in headings:
			row[heading] = hierarchyToHeading(heading)
		rows[:0] = [row]
		# create a new view to write the grid to
		gridView = self.view.window().new_file()
		
		valueForCell = lambda heading, row: row.get(heading, '')
		# if grid-mode
		if separator == ' ':
			linesForCell = lambda heading, row: valueForCell(heading, row).split('\n')
			
			# determine the size of each column
			colSizes = []
			for heading in headings:
				colSize = 0
				for row in rows:
					colSize = max(colSize, max(list(map(len, linesForCell(heading, row)))))
				colSizes.append(colSize) # add room for a space and vertical line between the cells/columns
			
			if includeGridLines:
				# add a divider line under the headings
				for columnNumber in range(len(headings)):
					rows[0][headings[columnNumber]] += '\n' + ('-' * colSizes[columnNumber])
				
			# determine the size of each row
			rowSizes = []
			for row in rows:
				rowSize = 0
				for heading in headings:
					rowSize = max(rowSize, len(linesForCell(heading, row)))
				rowSizes.append(rowSize)
			
			# if some cells span multiple lines
			if max(rowSizes[1:]) > 1 or alwaysIncludeLineNumbers:
				# insert a column of line numbers
				lineNoHeading = ('#')
				headings[:0] = [lineNoHeading]
				colSize = len(str(len(rows)))
				for rowIndex, row in enumerate(rows):
					row[lineNoHeading] = (' ' * (colSize - len(str(rowIndex)))) + str(rowIndex) # align right
				
				rows[0][lineNoHeading] = '#'
				if includeGridLines:
					rows[0][lineNoHeading] += '\n' + ('-' * colSize)
					
				colSizes[:0] = [colSize]
			
			# write the cells
			currentLine = 0
			append = ' '
			if includeGridLines:
				append += '| '
			for rowNumber in range(len(rowSizes)): # for each row
				for rowLine in range(rowSizes[rowNumber]): # for each line in the row
					for columnNumber in range(len(headings)): # for each column
						lines = linesForCell(headings[columnNumber], rows[rowNumber])
						if len(lines) <= rowLine:
							cellLineText = ''
						else:
							cellLineText = lines[rowLine]
						gridView.insert(edit, gridView.size(), cellLineText + ' ' * (colSizes[columnNumber] - len(cellLineText)) + append) # write the text followed by enough blank spaces to fill the rest of the column
					currentLine += 1
					gridView.insert(edit, gridView.size(), '\n')
		# if csv-mode
		else:
			# write the rows
			for row in rows:
				gridView.insert(edit, gridView.size(), separator.join(map(lambda heading: getCSVValue(valueForCell(heading, row), separator), headings)) + '\n')
		
		sublime.status_message('')
	def is_enabled(self):
		return isSGML(self.view)
	def is_visible(self):
		return isSGML(self.view)
	
