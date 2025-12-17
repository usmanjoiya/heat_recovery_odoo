#!/usr/bin/env python
# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################

"""
  Code from https://github.com/nkchenz/lhammer/blob/master/lhammer/xml2dict.py
  Distributed under GPL2 Licence
  CopyRight (C) 2009 Chen Zheng
  Adapted for Prestapyt by Guewen Baconnier
  Copyright 2012 Camptocamp SA
"""
import re
try:
	import xml.etree.cElementTree as ET
except ImportError as err:
	import xml.etree.ElementTree as ET


def _parse_node(node):
	tree = {}
	attrs = {}
	for attr_tag, attr_value in list(node.attrib.items()):
		#  skip href attributes, not supported when converting to dict
		if attr_tag == '{http://www.w3.org/1999/xlink}href':
			continue
		attrs.update(_make_dict(attr_tag, attr_value))

	value = node.text.strip() if node.text is not None else ''

	if attrs:
		tree['attrs'] = attrs

	#Save childrens
	has_child = False
	for child in node.getchildren():
		has_child = True
		ctag = child.tag
		ctree = _parse_node(child)
		cdict = _make_dict(ctag, ctree)

		# no value when there is child elements
		if ctree:
			value = ''

		# first time an attribute is found
		if ctag not in tree: # First time found
			tree.update(cdict)
			continue

		# many times the same attribute, we change to a list
		old = tree[ctag]
		if not isinstance(old, list):
			tree[ctag] = [old] # change to list
		tree[ctag].append(ctree) # Add new entry

	if not has_child:
		tree['value'] = value

	# if there is only a value; no attribute, no child, we return directly the value
	if list(tree.keys()) == ['value']:
		tree = tree['value']
	return tree

def _make_dict(tag, value):
	"""Generate a new dict with tag and value
	   If tag is like '{http://cs.sfsu.edu/csc867/myscheduler}patients',
	   split it first to: http://cs.sfsu.edu/csc867/myscheduler, patients
	"""
	tag_values = value
	result = re.compile("\\{(.*)\\}(.*)").search(tag)
	if result:
		tag_values = {'value': value}
		tag_values['xmlns'], tag = result.groups() # We have a namespace!
	return {tag: tag_values}

def xml2dict(xml):
	"""Parse xml string to dict"""
	element_tree = ET.fromstring(xml)
	return ET2dict(element_tree)

def ET2dict(element_tree):
	"""Parse xml string to dict"""
	return _make_dict(element_tree.tag, _parse_node(element_tree))