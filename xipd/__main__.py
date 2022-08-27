import sys
import argparse

from .renderer import Renderer
from .format import autoformat


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument(
		'infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin,
	)
	args = parser.parse_args()

	renderer = Renderer()
	output = renderer.render(args.infile)
	output = autoformat(output)
	print(output, end='')


if __name__ == '__main__':
	main()
