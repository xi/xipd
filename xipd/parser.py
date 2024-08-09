import re

# https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Operator_Precedence#table
OPERATORS = [
	('*~', 12),
	('*', 12),
	('/~', 12),
	('/', 12),
	('+~', 11),
	('+', 11),
	('-~', 11),
	('-', 11),
	('<<', 10),
	('>>', 10),
	('&', 7),
	('|', 5),
]


class SyntaxError(TypeError):
	pass


class Parser:
	def parse_re(self, s, pattern):
		m = re.match(pattern, s)
		if m:
			head = s[:m.end()]
			tail = s[m.end():]
			return head, tail
		else:
			raise SyntaxError('expected "%s"' % pattern, s)

	def parse_any(self, s, parsers, parse_to_end=False):
		errors = []
		for parser in parsers:
			try:
				value, s = parser(s)
				if parse_to_end and s:
					raise SyntaxError('tail', s)
				return value, s
			except SyntaxError as e:
				errors.append(e)
				pass
		raise SyntaxError(errors)

	def parse_list(self, s, parse_item):
		_, s = self.parse_re(s, r'\(')
		items = []
		while not s.startswith(')'):
			if items:
				_, s = self.parse_re(s, r', *')
			item, s = parse_item(s)
			items.append(item)
		_, s = self.parse_re(s, r'\)')
		return items, s

	def parse_name(self, s):
		return self.parse_re(s, r'[a-zA-Z_][a-zA-Z0-9_]*')

	def parse_port(self, s):
		port, s = self.parse_re(s, r':[0-9]+')
		return int(port[1:]), s

	def parse_str(self, s):
		value, s = self.parse_re(s, r'"[^"]*"')
		return ('str', value[1:-1]), s

	def parse_int(self, s):
		value, s = self.parse_re(s, r'[0-9]+')
		return ('int', int(value)), s

	def parse_float(self, s):
		value, s = self.parse_re(s, r'[0-9]+(\.[0-9]+)')
		return ('float', float(value)), s

	def parse_raw(self, s):
		value, s = self.parse_re(s, r'`[^`]*`')
		return ('raw', value[1:-1]), s

	def parse_ref(self, s):
		name, s = self.parse_name(s)
		if s.startswith(':'):
			port, s = self.parse_port(s)
		else:
			port = None
		return ('ref', name, port), s

	def parse_connect(self, s):
		left, s = self.parse_expr(s)
		_, s = self.parse_re(s, r' *-> *')
		right, s = self.parse_expr(s)
		return ('connect', left, right), s

	def parse_expr_no_op(self, s):
		return self.parse_any(s, [
			self.parse_parens,
			self.parse_call,
			self.parse_ref,
			self.parse_str,
			self.parse_float,
			self.parse_int,
			self.parse_raw,
		])

	def parse_parens(self, s):
		_, s = self.parse_re(s, r'\(')
		expr, s = self.parse_expr(s)
		_, s = self.parse_re(s, r'\)')
		return expr, s

	def parse_op(self, s):
		s = s.lstrip()
		for op, precedence in OPERATORS:
			if s.startswith(op):
				s = s[len(op):].lstrip()
				return (op, precedence), s
		else:
			raise SyntaxError

	def _apply_operator_precedence(self, ops, exprs):
		expr_stack = [exprs[0]]
		op_stack = []

		def pop():
			op, _ = op_stack.pop()
			rhs = expr_stack.pop()
			lhs = expr_stack.pop()
			expr_stack.append(('op', op, lhs, rhs))

		for i, op in enumerate(ops):
			while op_stack and op_stack[-1][1] >= op[1]:
				pop()
			op_stack.append(op)
			expr_stack.append(exprs[i + 1])

		while op_stack:
			pop()

		assert len(expr_stack) == 1
		return expr_stack[0]

	def parse_expr(self, s):
		expr, s = self.parse_expr_no_op(s)
		exprs = [expr]
		ops = []

		while True:
			try:
				op, s_tmp = self.parse_op(s)
				expr, s_tmp = self.parse_expr_no_op(s_tmp)
				ops.append(op)
				exprs.append(expr)
				s = s_tmp
			except SyntaxError:
				break

		return self._apply_operator_precedence(ops, exprs), s

	def parse_assign(self, s):
		name, s = self.parse_name(s)
		_, s = self.parse_re(s, r' *= *')
		expr, s = self.parse_expr(s)
		return ('assign', name, expr), s

	def parse_startfunc(self, s):
		name, s = self.parse_name(s)
		args, s = self.parse_list(s, self.parse_name)
		_, s = self.parse_re(s, ' *{')
		return ('startfunc', name, args), s

	def parse_endfunc(self, s):
		_, s = self.parse_re(s, '}')
		return ('endfunc',), s

	def parse_call(self, s):
		name, s = self.parse_name(s)
		args, s = self.parse_list(s, self.parse_expr)
		return ('call', name, args), s

	def parse_include(self, s):
		_, s = self.parse_re(s, r'include *')
		path, s = self.parse_str(s)
		return ('include', path[1]), s

	def parse_array(self, s):
		_, s = self.parse_re(s, r'array *')
		name, s = self.parse_str(s)
		return ('array', name[1]), s

	def parse_return(self, s):
		_, s = self.parse_re(s, r'return *')
		expr, s = self.parse_expr(s)
		return ('return', expr), s

	def parse_line(self, s):
		ast, s = self.parse_any(s, [
			self.parse_include,
			self.parse_array,
			self.parse_return,
			self.parse_connect,
			self.parse_assign,
			self.parse_startfunc,
			self.parse_endfunc,
			self.parse_expr,
		], parse_to_end=True)
		return ast

	def parse_file(self, fh):
		stack = [[]]
		for lineno, line in enumerate(fh):
			line = line.strip()
			if not line or line.startswith('#'):
				continue
			parsed = self.parse_line(line)

			if parsed[0] == 'startfunc':
				stack[-1].append(parsed)
				stack.append([])
			elif parsed[0] == 'endfunc':
				body = stack.pop()
				startfunc = stack[-1].pop()
				stack[-1].append(('func', *startfunc[1:], body))
			else:
				stack[-1].append(parsed)
		if not len(stack) == 1:
			raise SyntaxError('unbalanced blocks')
		return stack[0]
