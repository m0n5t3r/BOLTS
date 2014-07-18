#bolttools - a framework for creation of part libraries
#Copyright (C) 2013 Johannes Reinhardt <jreinhardt@ist-dein-freund.de>
#
#This library is free software; you can redistribute it and/or
#modify it under the terms of the GNU Lesser General Public
#License as published by the Free Software Foundation; either
#version 2.1 of the License, or any later version.
#
#This library is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#Lesser General Public License for more details.
#
#You should have received a copy of the GNU Lesser General Public
#License along with this library; if not, write to the Free Software
#Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

#common elements and baseclasses

import re
import math
import string
import collections
from os.path import join
from copy import deepcopy

from errors import *


def parse_angled(string):
	"""
	Parse strings of the form "Something <something.else>", which are often
	used for names and email addresses
	"""
	RE_ANGLED = re.compile("([^<]*)<([^>]*)>")
	match = RE_ANGLED.match(string)
	if match is None:
		raise MalformedStringError("Expected string containing <>")
	return match.group(1).strip(), match.group(2).strip()

def check_schema(yaml_dict, element_name, mandatory_fields, optional_fields):
	"""Check a dict resulting from YAML parsing for correct and complete fields"""
	for key in yaml_dict.keys():
		if key in mandatory_fields:
			mandatory_fields.remove(key)
		elif key in optional_fields:
			optional_fields.remove(key)
		else:
			raise UnknownFieldError(element_name,key)
	if len(mandatory_fields) > 0:
		raise MissingFieldError(element_name,mandatory_fields)

def check_iterator_arguments(items,primary,optional,kwargs):
	#check items
	if primary not in items:
		raise ValueError("Primary object of iterator not found in items: %s" % primary)
	for it in items:
		if it == primary:
			continue
		if not it in optional:
			raise ValueError("Unknown item requested in iterator: %s" % it)
	#check filters
	filters = ["filter_%s" % o for o in optional]
	for k in kwargs:
		if not k in filters:
			raise ValueError("Unknown argument %s for iterator" % k)

def filter_iterator_items(its,kwargs):
	for i in its:
		fil = "filter_" + i
		if fil in kwargs:
			if type(its[i]) == type(kwargs[fil]):
				return kwargs[fil] is its[i]
			elif type(its[i]) != type(kwargs[fil]) and isinstance(its[i],collections.Container):
				return kwargs[fil] in its[i]
			else:
				raise ValueError("Strange filter argument: %s" % kwargs[fil])
	return True

ALL_TYPES = ["Length (mm)", "Length (in)", "Number", "Bool", "Table Index", "String","Angle (deg)"]

def convert_raw_parameter_value(pname,tname,value):
	""" Convert from strings from YAML parsing to python types and check conformity with the corresponding BOLTS type"""
	numbers = ["Length (mm)", "Length (in)", "Number","Angle (deg)"]
	positive = ["Length (mm)", "Length (in)"]

	#Check
	if not tname in ALL_TYPES:
		raise UnknownTypeError(tname)

	#Convert
	if value == "None":
		value = None
	elif tname in numbers:
		value = float(value)
		if tname in positive and value < 0:
			raise ValueError("Negative length in table for parameter %s: %f" % (pname,value))
		elif tname == "Angle (deg)" and math.fabs(value) > 360:
			raise ValueError("Angles must be 360 > alpha > -360: %s is %f" % (pname,value))
	elif tname == "Bool":
		if value == "true":
			value = True
		elif value == "false":
			value = False
		else:
			raise ValueError("Unknown value for bool parameter %s: %s" % (pname,value))

	return value

class Links:
	"""
	Class to represent a 1 to N mapping between objects, where every
	destination has at most one source that is mapped onto it, i.e. its
	inverse is injective.
	"""
	def __init__(self,N=None):
		"""
		Create a new Links instance. N gives an upper bound for the
		number of destinations for a source, None represents infinity.
		"""
		assert(N is None or N > 0)
		self.N = N
		self.srctodsts = {}
		self.dsttosrc = {}

	def add_link(self,src,dst):
		"""
		Add a link from src to dst
		"""
		if src in self.srctodsts:
			if not self.N is None and len(self.srctodsts[src]) >= self.N:
				raise LimitExceededError(src,dst)
			self.srctodsts[src].append(dst)
		else:
			self.srctodsts[src] = [dst]
		if dst in self.dsttosrc:
			raise ValueError("Destination already used %s" % dst)
		self.dsttosrc[dst] = src

	def contains_src(self,src):
		"""
		Indicates whether there is a link with source src
		"""
		return src in self.srctodsts

	def contains_dst(self,dst):
		"""
		Indicates whether there is a link with destination dst
		"""
		return dst in self.dsttosrc

	def get_dsts(self,src):
		"""
		Return a list of destinations of the mapping for this src.
		"""
		return self.srctodsts[src]

	def get_src(self,dst):
		"""
		Return the source that gets mapped onto this dst.
		"""
		return self.dsttosrc[dst]

class BipartiteLinks:
	"""
	Class to represent a N to N mapping between objects, where every
	object is either source or destination.
	"""
	def __init__(self):
		"""
		Create a new BipartiteLinks instance.
		"""
		self.srctodsts = {}
		self.dsttosrcs = {}

	def add_link(self,src,dst):
		"""
		Add a link from src to dst
		"""
		if src in self.dsttosrcs:
			raise ValueError("Source already used as destination %s" % dst)
		if dst in self.srctodsts:
			raise ValueError("Destination already used as source %s" % dst)
		if src in self.srctodsts:
			self.srctodsts[src].append(dst)
		else:
			self.srctodsts[src] = [dst]
		if dst in self.dsttosrcs:
			self.dsttosrcs[dst].append(src)
		else:
			self.dsttosrcs[dst] = [src]

	def contains_src(self,src):
		"""
		Indicates whether there is a link with source src
		"""
		return src in self.srctodsts

	def contains_dst(self,dst):
		"""
		Indicates whether there is a link with destination dst
		"""
		return dst in self.dsttosrcs

	def get_dsts(self,src):
		"""
		Return a list of destinations of the mapping for this src.
		"""
		return self.srctodsts[src]

	def get_srcs(self,dst):
		"""
		Return a list of sources of the mapping for this dst.
		"""
		return self.dsttosrcs[dst]

class BijectiveLinks:
	"""
	Class to represent a 1 to 1 mapping between objects, where every
	object is either source or destination.
	"""
	def __init__(self):
		"""
		Create a new BipartiteLinks instance.
		"""
		self.srctodst = {}
		self.dsttosrc = {}

	def add_link(self,src,dst):
		"""
		Add a link from src to dst
		"""
		if src in self.dsttosrc:
			raise ValueError("Source already used as destination %s" % dst)
		if dst in self.srctodst:
			raise ValueError("Destination already used as source %s" % dst)

		if src in self.srctodst:
			raise ValueError("Source %s already has as destination %s" % (src,self.srctodst[src]))
		else:
			self.srctodst[src] = dst
		if dst in self.dsttosrc:
			raise ValueError("Source %s already has as destination %s" % (src,self.srctodst[src]))
		else:
			self.dsttosrc[dst] = src

	def contains_src(self,src):
		"""
		Indicates whether there is a link with source src
		"""
		return src in self.srctodst

	def contains_dst(self,dst):
		"""
		Indicates whether there is a link with destination dst
		"""
		return dst in self.dsttosrc

	def get_dst(self,src):
		"""
		Return the destination of the mapping for this src.
		"""
		return self.srctodst[src]

	def get_src(self,dst):
		"""
		Return the source of the mapping for this dst.
		"""
		return self.dsttosrc[dst]

class Sorting:
	"""Base class for classes for sorting choices for a Table Index"""
	def __init__(self):
		pass
	def is_applicable(self,choices):
		"""check whether this way of sorting is applicable to a set of choices"""
		raise NotImplementedError
	def sort(self,choices):
		"""returns a sorted copy of choices"""
		raise NotImplementedError

class Numerical(Sorting):
	"""Sorts according to the numbers that are contained in the key"""
	def __init__(self):
		Sorting.__init__(self)
		self.re = re.compile("[^0-9]*([0-9]+\.*[0-9]*)[^0-9]*$")
	def is_applicable(self,choices):
		for choice in choices:
			if self.re.match(choice) is None:
				return False
		return True
	def sort(self,choices):
		return sorted(choices, key=lambda x: float(self.re.match(x).group(1)))

class Lexicographical(Sorting):
	"""Sorts keys in lexicographical order"""
	def __init__(self):
		Sorting.__init__(self)
	def is_applicable(self,choices):
		return True
	def sort(self,choices):
		return sorted(choices)

SORTINGS = [Numerical(), Lexicographical()]

class Parameters:
	"""
	Python class that holds all the informations about the parameters of a
	BOLTS class, and implements common operations on them
	"""
	type_defaults = {
		"Length (mm)" : 10,
		"Length (in)" : 1,
		"Number" : 1,
		"Bool" : False,
		"Table Index": '',
		"String" : '',
		"Angle (deg)" : 0
	}
	def __init__(self,param):
		"""
		Create a new Parameters instance

		param: dictionary from YAML parsing
		"""
		check_schema(param,"parameters",
			["types"],
			["literal","free","tables","tables2d","defaults","common","description"]
		)

		self.types = {}
		if "types" in param:
			self.types = param["types"]

		self.literal = {}
		if "literal" in param:
			for pname,val in param["literal"].iteritems():
				if not pname in self.types:
					raise MissingTypeError(pname)
				self.literal[pname] = convert_raw_parameter_value(pname,self.types[pname],val)

		self.free = []
		if "free" in param:
			self.free = param["free"]

		self.tables = []
		if "tables" in param:
			if isinstance(param["tables"],list):
				for table in param["tables"]:
					self.tables.append(Table(table))
			else:
				self.tables.append(Table(param["tables"]))

		self.tables2d = []
		if "tables2d" in param:
			if isinstance(param["tables2d"],list):
				for table in param["tables2d"]:
					self.tables2d.append(Table2D(table))
			else:
				self.tables2d.append(Table2D(param["tables2d"]))

		self.description = {}
		if "description" in param:
			self.description = param["description"]

		self.parameters = []
		self.parameters += self.literal.keys()
		self.parameters += self.free
		for table in self.tables:
			self.parameters.append(table.index)
			self.parameters += table.columns
		for table in self.tables2d:
			self.parameters.append(table.rowindex)
			self.parameters.append(table.colindex)
			self.parameters.append(table.result)
		#remove duplicates
		self.parameters = list(set(self.parameters))

		#check types
		for pname,tname in self.types.iteritems():
			if not pname in self.parameters:
				raise UnknownParameterError(pname)
			if not tname in ALL_TYPES:
				raise UnknownTypeError(tname)

		for pname in self.parameters:
			if not pname in self.types:
				raise MissingTypeError(pname)

		#check description
		for pname,tname in self.description.iteritems():
			if not pname in self.parameters:
				raise UnknownParameterError(pname)

		#check and normalize tables
		for table in self.tables:
			table._normalize_and_check_types(self.types)
			if self.types[table.index] != "Table Index":
				raise TableIndexTypeError(table.index,self.types[table.index])
		for table in self.tables2d:
			table._normalize_and_check_types(self.types)
			if self.types[table.rowindex] != "Table Index":
				raise TableIndexTypeError(table.rowindex,self.types[table.rowindex])
			if self.types[table.colindex] != "Table Index":
				raise TableIndexTypeError(table.colindex,self.types[table.colindex])

		#find the set of possible choices for every Table Index
		self.choices = {}
		for pname in self.free:
			if not self.types[pname] == "Table Index":
				continue
			for table in self.tables:
				if table.index == pname:
					if not pname in self.choices:
						self.choices[pname] = set(table.data.keys())
					else:
						self.choices[pname] &= set(table.data.keys())
			for table in self.tables2d:
				if table.rowindex == pname:
					if not pname in self.choices:
						self.choices[pname] = set(table.data.keys())
					else:
						self.choices[pname] &= set(table.data.keys())
				elif table.colindex == pname:
					if not pname in self.choices:
						self.choices[pname] = set(table.columns)
					else:
						self.choices[pname] &= set(table.columns)
		#figure out what the best way is to sort them
		for pname in self.choices:
			for sort in SORTINGS:
				if sort.is_applicable(self.choices[pname]):
					self.choices[pname] = sort.sort(self.choices[pname])
					break

		#default values for free parameters
		self.defaults = dict((pname,self.type_defaults[self.types[pname]])
			for pname in self.free)
		if "defaults" in param:
			for pname,dvalue in param["defaults"].iteritems():
				if pname not in self.free:
					raise NonFreeDefaultError(pname)
				if self.types[pname] == "Table Index" and dvalue not in self.choices[pname]:
					raise InvalidTableIndexError(pname,dvalue)
				self.defaults[pname] = dvalue

		#common parameter combinations
		discrete_types = ["Bool", "Table Index"]
		self.common = None
		if "common" in param:
			self.common = []
			for tup in param["common"]:
				self._populate_common(tup,[],0)
		else:
			discrete = True
			for pname in self.free:
				if not self.types[pname] in discrete_types:
					discrete = False
					break
			if discrete:
				self.common = []
				if len(self.free) > 0:
					self._populate_common([":" for _i in range(len(self.free))],[],0)
				else:
					self.common.append([])

	def _populate_common(self, tup, values, idx):
		#helper function for recursively populating the dict of common parameters
		if idx == len(self.free):
			self.common.append(values)
		else:
			if tup[idx] == ":":
				if self.types[self.free[idx]] == "Bool":
					for v in [True, False]:
						self._populate_common(tup,values + [v], idx+1)
				elif self.types[self.free[idx]] == "Table Index":
					#populate
					for v in self.choices[self.free[idx]]:
						self._populate_common(tup,values + [v], idx+1)
				else:
					print "That should not happen"
			else:
				for v in tup[idx]:
					self._populate_common(tup,values + [v], idx+1)

	def collect(self,free):
		"""
		Derive parameter values for all parameters from given values
		for the free parameters
		"""
		res = {}
		res.update(self.literal)
		res.update(free)
		for table in self.tables:
			res.update(table.get_values(res[table.index]))
		for table in self.tables2d:
			res.update(table.get_value(res[table.rowindex],res[table.colindex]))
		for pname in self.parameters:
			if not pname in res:
				raise KeyError("Parameter value not collected: %s" % pname)
		return res

	def union(self,other):
		"""
		Return a new Parameter instance that is the union of this
		and another Parameter instance
		"""
		res = Parameters({"types" : {}})
		res.literal.update(self.literal)
		res.literal.update(other.literal)
		res.free = self.free + other.free
		res.tables = self.tables + other.tables
		res.tables2d = self.tables2d + other.tables2d
		res.parameters = list(set(self.parameters + other.parameters))

		for pname,tname in self.types.iteritems():
			res.types[pname] = tname
		for pname,tname in other.types.iteritems():
			if pname in res.types and self.types[pname] != tname:
				raise IncompatibleTypeError(pname,self.types[pname],tname)
			res.types[pname] = tname

		for pname,dname in self.defaults.iteritems():
			res.defaults[pname] = dname
		for pname,dname in other.defaults.iteritems():
			if pname in res.defaults and self.defaults[pname] != dname:
				raise IncompatibleDefaultError(pname,self.defaults[pname],dname)
			res.defaults[pname] = dname

		for pname,descr in self.description.iteritems():
			res.description[pname] = descr
		for pname,descr in other.description.iteritems():
			if pname in res.description and self.description[pname] != descr:
				raise IncompatibleDescriptionError(pname,self.description[pname],descr)
			res.description[pname] = descr

		res.choices = {}
		for pname in self.choices:
			res.choices[pname] = set(self.choices[pname])
		for pname in other.choices:
			if pname in res.choices:
				res.choices[pname] &= set(other.choices[pname])
			else:
				res.choices[pname] = set(other.choices[pname])
		for pname in res.choices:
			for sort in SORTINGS:
				if sort.is_applicable(res.choices[pname]):
					res.choices[pname] = sort.sort(res.choices[pname])
					break
		return res

class Table:
	"""
	Class representing a table where the values for a number of parameter
	(in the columns) can be looked up for a given row key.
	"""
	def __init__(self,table):
		"""
		Create a new Table instance

		table: dictionary from YAML parsing
		"""
		check_schema(table,"table",
			["index","columns","data"],
			[]
		)

		self.index = table["index"]
		self.columns = table["columns"]
		self.data = deepcopy(table["data"])

	def _normalize_and_check_types(self,types):
		col_types = [types[col] for col in self.columns]
		for key in self.data:
			#check key
			for char in key:
				if char in '\\/?*:|"\'<>\t\n\r':
					raise MalformedTableIndexError(key)

			#check row
			row = self.data[key]
			if len(row) != len(self.columns):
				raise ValueError("Column is missing for row: %s" % key)
			for i in range(len(self.columns)):
				row[i] = convert_raw_parameter_value(self.columns[i],col_types[i],row[i])

	def get_values(self,key):
		"""
		Look up parameter values for a given row key

		returns: dictionary with parametername : value pairs
		"""
		return dict(zip(self.columns,self.data[key]))

class Table2D:
	"""
	Class representing a 2D table where the values for a parameter can be
	looked up for a given row and column key.
	"""
	def __init__(self,table):
		"""
		Create a new Table2D instance

		table: dictionary from YAML parsing
		"""
		check_schema(table,"table2d",
			["rowindex","colindex","columns","result","data"],
			[]
		)

		self.rowindex = table["rowindex"]
		self.colindex = table["colindex"]
		self.result = table["result"]
		self.columns = table["columns"]
		self.data = deepcopy(table["data"])

		if self.rowindex == self.colindex:
			raise ValueError("Row- and ColIndex are identical. In this case a ordinary table should be used.")

	def _normalize_and_check_types(self,types):
		#check column keys
		for key in self.columns:
			for char in key:
				if char in '\\/?*:|"\'<>\t\n\r':
					raise MalformedTableIndexError(key)
		res_type = types[self.result]
		for key in self.data:
			#check key
			for char in key:
				if char in '\\/?*:|"\'<>\t\n\r':
					raise MalformedTableIndexError(key)
			#check row
			row = self.data[key]
			if len(row) != len(self.columns):
				raise ValueError("Column is missing for row: %s" % key)
			for i in range(len(self.columns)):
				row[i] = convert_raw_parameter_value(self.result,types[self.result],row[i])
	def get_value(self,row,col):
		"""
		Look up parameter value for a given row key

		returns: dictionary with parametername : value pair
		"""
		row = self.data[row]
		return {self.result : row[self.columns.index(col)]}

class NamePair:
	"""
	Class to represent a pair of names for use in different situations.

	yd: dictionary from yaml
	allowed: set of characters that are allowed in the safe name
	"""
	def __init__(self,safe,nice,allowed):
		self.allowed = allowed
		self.nice = nice
		self.safe = safe

		#check for only allowed characters
		for c in self.safe:
			if not c in self.allowed:
				raise ValueError('String %s contains forbidden characters: %s' % (self.safe,c))

	def get_safe(self):
		"""return the safe name"""
		return self.safe
	def get_nice(self):
		"""return the nice name"""
		return self.nice
	
	def __eq__(self,other):
		return self.safe == other.safe and self.nice == other.nice
	
	def __ne__(self,other):
		return self.safe != other.safe or self.nice != other.nice



class Identifier(NamePair):
	"""Python class for identifying a BOLTS class"""
	def __init__(self,ident):
		check_schema(ident,"identifier",
			["nice"],
			["safe"]
		)

		allowed = set(string.ascii_letters + string.digits + '_')

		sane = self._sanitize(ident['nice'],allowed)

		if "safe" in ident:
			NamePair.__init__(self,ident['safe'],ident['nice'],allowed)
		else:
			NamePair.__init__(self,sane,ident['nice'],allowed)


	def _sanitize(self,inp,allowed):
		#try to make it camelCase
		parts = inp.split()
		res = []
		for p in parts:
			if p.isupper():
				res.append(p)
			else:
				res.append(p.capitalize())

		res = "".join(res)
		#remove all disallowed characters
		for c in res[:]:
			if not c in allowed:
				res = res.replace(c,'')
		return res



class Substitution(NamePair):
	"""Python class for identifying a part derived from a BOLTS class"""
	def __init__(self,subst):
		check_schema(subst,"substitution",
			['nice'],
			['safe']
		)

		allowed = set(string.printable).difference(set("""/\\?*|"'>"""))

		sane = self._sanitize(subst['nice'],allowed)

		if "safe" in subst:
			NamePair.__init__(self,subst['safe'],subst['nice'],allowed)
		else:
			NamePair.__init__(self,sane,subst['nice'],allowed)

	def _sanitize(self,inp,allowed):
		inp = "_".join(inp.split())
		#remove all disallowed characters
		for c in inp[:]:
			if not c in allowed:
				inp = inp.replace(c,'')
		return inp

	def get_safe(self,params):
		res = self.safe % params
		for c in res:
			if c in string.whitespace:
				res = res.replace(c,'_')
		return res
	def get_nice(self,params):
		return self.nice % params

class DataBase:
	def __init__(self,name,repo):
		self.name = name
		self.repo = repo

		self.repo_root = self.repo.path
		#TODO: rename to data_root
		self.backend_root = join(self.repo.path,name)

class BaseElement:
	"""
	Base class for representing BaseElements, yaml structures that describe
	the contents of file
	"""
	def __init__(self,basefile):
		self.authors = basefile["author"]
		if isinstance(self.authors,str):
			self.authors = [self.authors]
		self.author_names = []
		self.author_mails = []
		for author in self.authors:
			match = parse_angled(author)
			self.author_names.append(match[0])
			self.author_mails.append(match[1])

		self.license = basefile["license"]
		match = parse_angled(self.license)
		self.license_name = match[0]
		self.license_url = match[1]

		self.type = basefile["type"]

		if "source" in basefile:
			self.source = basefile["source"]
		else:
			self.source = ""
