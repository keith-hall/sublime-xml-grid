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

def displayField(view, edit, value, separator, colsize):
	"""add text to grid view, lining up spaces if applicable."""
	if value is None:
		value = ''
	if separator == ' ':
		if '\n' in value:
			startCol = view.rowcol(view.size())[1]
			lines = value.split('\n')
			for index, line in enumerate(lines):
				append = separator * (colsize - len(line))
				if index < len(lines) - 1: # don't append a newline to the last line in the value
					append += '\n'
				view.insert(edit, view.size(), (separator * (startCol - view.rowcol(view.size())[1])) + line + append) # prepend enough spaces to start at the right column
			return
		else:
			separator = separator * (colsize - len(value))
	else:
		quote = '"'
		# the following text qualification rules and quote doubling are based on recommendations in RFC 4180
		if quote in value or value.endswith(' ') or value.endswith('\t') or value.startswith(' ') or value.startswith('\t') or '\n' in value or separator in value: # qualify the text in quotes if it contains a quote, starts or ends in whitespace, or contains the separator or a newline
			value = quote + value.replace(quote, quote + quote) + quote # to escape a quote, we double it up
	view.insert(edit, view.size(), value + separator)

def isSGML(view):
	"""return True if the view's syntax is XML."""
	currentSyntax = view.settings().get('syntax')
	if currentSyntax is not None:
		XMLSyntax = 'Packages/XML/'
		return currentSyntax.startswith(XMLSyntax)
	else:
		return False

def findNamespacePrefix(hierarchy, namespaceURI):
	for namespaces in hierarchy:
		for namespace in namespaces:
			if namespace[1] == namespaceURI:
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

def parseXMLFile(fileRef):
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
			
			attributes = {}
			for attribute in item.attrib:
				namespaceURI, local = extractNamespaceURI(attribute)
				prefix = findNamespacePrefix(hierarchy, namespaceURI)
				attributes[prefix + local] = item.attrib[attribute]
			
			# add xmlns attributes back in, as ElementTree removes them
			for namespaces in nextNamespaces:
				prefix = namespaces[0]
				if prefix != '':
					prefix = ':' + prefix
				attributes['xmlns' + prefix] = namespaces[1]
			item.attrib = attributes
			
			if len(nextNamespaces) > 0:
				nextNamespaces = []
		elif event == 'end':
			hierarchy.pop()
	return root

class XmlToGridCommand(sublime_plugin.TextCommand): #sublime.active_window().active_view().run_command('xml_to_grid')
	def run(self, edit):
		sublime.status_message('parsing xml...')
		# parse the view as xml
		xmlString = self.view.substr(sublime.Region(0, self.view.size()))
		
		root = parseXMLFile(StringIO(xmlString))
		
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
		
		# determine the size of each column if space is the separator
		colsizes = {}
		if separator == ' ':
			for item in headings:
				size = len(hierarchyToHeading(item))
				for row in rows:
					if item in row.keys():
						for line in row[item].split('\n'):
							itemSize = len(line)
							if itemSize > size:
								size = itemSize
				colsizes[item] = size + 1 # add one to ensure that there is a gap between fields
		
		# create a new view to write the grid to
		gridView = self.view.window().new_file()
		
		# write the headings
		for item in headings:
			if item not in colsizes:
				colsizes[item] = 0
			displayField(gridView, edit, hierarchyToHeading(item), separator, colsizes[item])
		gridView.insert(edit, gridView.size(), '\n')
		# write the rows
		for row in rows:
			for item in headings:
				if item in row.keys():
					value = row[item]
				else:
					value = ''
				displayField(gridView, edit, value, separator, colsizes[item])
			gridView.insert(edit, gridView.size(), '\n')
		
		sublime.status_message('')
	def is_enabled(self):
		return isSGML(self.view)
	def is_visible(self):
		return isSGML(self.view)
