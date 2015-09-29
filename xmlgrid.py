import sublime, sublime_plugin
import xml.etree.ElementTree as etree

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
		base = item
		if '}' in base:
			base = base[0:base.index('{')] + base[base.index('}') + 1:]
		if base.startswith('@'):
			base = '[' + base + ']'
		elif heading != '':
			heading += '/'
		heading += base
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
		separator = separator * (colsize - len(value))
	
	view.insert(edit, view.size(), value + separator)

def isSGML(view):
	"""Return True if the view's syntax is XML."""
	currentSyntax = view.settings().get('syntax')
	if currentSyntax is not None:
		XMLSyntax = 'Packages/XML/'
		return currentSyntax.startswith(XMLSyntax)
	else:
		return False

class XmlToGridCommand(sublime_plugin.TextCommand): #sublime.active_window().active_view().run_command('xml_to_grid')
	def run(self, edit):
		# parse the view as xml
		xml = etree.fromstring(self.view.substr(sublime.Region(0, self.view.size())))
		
		# find the elements that will become rows in the grid
		children = findMultipleChildren(xml)
		
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
						itemSize = len(row[item])
						if itemSize > size:
							size = itemSize
				colsizes[item] = size + 1
		
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
		
	def is_enabled(self):
		return isSGML(self.view)
	def is_visible(self):
		return isSGML(self.view)
