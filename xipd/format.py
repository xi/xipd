import re
import sys
import argparse
import subprocess

DOT_CMD = 'dot'


def pd2dot(pd):
	connections = []
	index = 0
	out = ['digraph _ {']
	for line in pd.splitlines():
		if line.startswith('#X connect'):
			parts = line.split()
			a = parts[2]
			b = parts[4]
			connections.append((a, b))
			out.append(f'  {b} -> {a};')
		elif line.startswith('#X obj') or line.startswith('#X msg'):
			out.append(f'  {index};')
			index += 1
		elif line.startswith('#X array'):
			index += 1
	out.append('}')
	return '\n'.join(out)


def parse_dot(dot):
	positions = {}
	dot = dot.replace(',\n', ', ')
	for line in dot.splitlines():
		m = re.match(r'\s*([0-9]+).*pos="([0-9.]+),([0-9.]+)"', line)
		if m:
			i = int(m.group(1))
			x = float(m.group(2))
			y = float(m.group(3))
			positions[i] = x, y
	return positions


def apply_positions(pd, positions):
	index = 0
	lines = []
	for line in pd.splitlines():
		if line.startswith('#X obj') or line.startswith('#X msg'):
			x, y = positions[index]
			parts = line.split()
			parts[2] = str(x)
			parts[3] = str(y)
			lines.append(' '.join(parts))
			index += 1
		else:
			if line.startswith('#X array'):
				index += 1
			lines.append(line)
	return ''.join(l + '\r\n' for l in lines)


def autoformat(pd):
	dot = pd2dot(pd)
	p = subprocess.run(DOT_CMD, input=dot, capture_output=True, text=True)
	positions = parse_dot(p.stdout)
	return apply_positions(pd, positions)


def try_autoformat(pd):
	try:
		return autoformat(pd)
	except FileNotFoundError:
		print(
			f'WARNING: {DOT_CMD} could not be found. Formatting is disabled.',
			file=sys.stderr,
		)
		return pd


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument(
		'infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin,
	)
	args = parser.parse_args()
	pd = args.infile.read()
	print(autoformat(pd), end='')


if __name__ == '__main__':
	main()
