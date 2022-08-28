import os

from .parser import Parser


def abspath(path, start):
	dir = os.path.dirname(start)
	joined = os.path.join(dir, path)
	return os.path.normpath(joined)


def find_include(path, start):
	p = abspath(path, start)
	if os.path.exists(p):
		return p
	else:
		return abspath(path, __file__)


class Scope:
	def __init__(self, parent=None):
		self.parent = parent
		self._refs = {}
		self._funcs = {}

	def add_ref(self, name, ref):
		self._refs[name] = ref

	def get_ref(self, name):
		if name in self._refs:
			return self._refs[name]
		elif self.parent:
			return self.parent.get_ref(name)
		else:
			raise KeyError(name)

	def add_func(self, name, value):
		self._funcs[name] = value

	def get_func(self, name):
		if name in self._funcs:
			value = self._funcs[name]
			return *value, self
		elif self.parent:
			return self.parent.get_func(name)
		else:
			raise KeyError(name)


class Renderer:
	def __init__(self):
		self.parser = Parser()

	def create_node(self):
		self.node_count += 1
		return self.node_count - 1

	def _print(self, s):
		self.output += f'#{s};\r\n'

	def call(self, name, args, scope):
		params, body, path, lexical_scope = scope.get_func(name)
		if len(args) != len(params):
			raise SyntaxError(f'wrong number of arguments for function {name}')

		subscope = Scope(lexical_scope)
		for param, arg in zip(params, args):
			subscope.add_ref(param, self.expr_to_ref(arg, scope))
		value = self.render_with_scope(body, subscope, path)
		if value is None:
			raise SyntaxError(f'missing return in function {name}')
		return value

	def expr_to_ref(self, expr, scope):
		if expr[0] == 'op':
			_, op, left, right = expr
			fn = 'op_' if op.endswith('~') else 'op'
			return self.call(fn, [('raw', op), left, right], scope)
		elif expr[0] == 'parens':
			return self.expr_to_ref(expr[1], scope)
		elif expr[0] == 'call':
			_, name, args = expr
			return self.call(name, args, scope)
		elif expr[0] == 'ref':
			_, name, port = expr
			index, default_port = scope.get_ref(name)
			if port is None:
				port = default_port or 0
			return index, port
		elif expr[0] == 'raw':
			self._print(f'X obj 0 0 {expr[1]}')
			index = self.create_node()
			return index, 0
		elif expr[0] in ['str', 'int', 'float']:
			self._print(f'X msg 0 0 {expr[1]}')
			index = self.create_node()
			self._print('X connect %i %i %i %i' % (
				*scope.get_ref('!loadbang'),
				index, 0
			))
			return index, 0
		else:
			raise SyntaxError('invalid expression', expr)

	def render_with_scope(self, ast, scope, path):
		for stmt in ast:
			if stmt[0] == 'include':
				_path = find_include(stmt[1], path)
				with open(_path) as fh:
					ast = self.parser.parse_file(fh)
				self.render_with_scope(ast, scope, _path)
			elif stmt[0] == 'return':
				_, expr = stmt
				return self.expr_to_ref(expr, scope)
			elif stmt[0] == 'connect':
				_, left, right = stmt
				self._print('X connect %i %i %i %i' % (
					*self.expr_to_ref(left, scope),
					*self.expr_to_ref(right, scope),
				))
			elif stmt[0] == 'assign':
				_, name, expr = stmt
				ref = self.expr_to_ref(expr, scope)
				scope.add_ref(name, ref)
			elif stmt[0] == 'func':
				_, name, params, body = stmt
				scope.add_func(name, (params, body, path))
			else:
				raise SyntaxError('invalid statement', stmt)

	def render(self, fh):
		scope = Scope()
		self.node_count = 0
		self.output = ''

		ast = self.parser.parse_file(fh)
		self._print('N canvas')
		self.render_with_scope([
			('assign', '!loadbang', ('raw', 'loadbang'))
		], scope, None)
		self.render_with_scope(ast, scope, fh.name)

		return self.output
