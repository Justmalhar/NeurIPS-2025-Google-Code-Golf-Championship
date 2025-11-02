import zlib
import argparse
import ast
import sys

class ZlibExtractor(ast.NodeVisitor):
    """
    An AST node visitor to find the specific zlib.decompress(bytes(..."L1"))
    pattern in the Python source code.
    """
    def __init__(self):
        self.compressed_string = None
        self.encoding = None

    def visit_Call(self, node):
        """Visit a function call node."""
        
        # We are looking for a very specific pattern:
        # A call to 'bytes' with two arguments.
        if isinstance(node.func, ast.Name) and node.func.id == 'bytes':
            if len(node.args) == 2:
                arg1 = node.args[0]
                arg2 = node.args[1]

                # Check if the first arg is a string (ast.Str for Py < 3.8, ast.Constant for Py 3.8+)
                is_str_arg1 = isinstance(arg1, (ast.Str, ast.Constant))
                # Check if the second arg is a string
                is_str_arg2 = isinstance(arg2, (ast.Str, ast.Constant))

                if is_str_arg1 and is_str_arg2:
                    # Get the string value for the encoding
                    if isinstance(arg2, ast.Str):
                        enc_val = arg2.s
                    else:
                        enc_val = arg2.value
                    
                    # Check if the encoding is 'L1'
                    if isinstance(enc_val, str) and enc_val.upper() == 'L1':
                        # Found it! Get the compressed string value.
                        if isinstance(arg1, ast.Str):
                            self.compressed_string = arg1.s
                        else:
                            self.compressed_string = arg1.value
                        
                        # 'L1' is an alias for 'latin-1'
                        self.encoding = 'latin-1'
                        return  # Stop searching once found

        # Continue traversing the tree if not found
        self.generic_visit(node)

def decompress_file(input_path, output_path):
    """
    Reads, parses, and decompresses the input file,
    writing the result to the output file.
    """
    try:
        # The file uses #coding:L1, which maps to 'latin-1'
        with open(input_path, 'r', encoding='latin-1') as f:
            file_content = f.read()
    except FileNotFoundError:
        print(f"Error: Input file not found at '{input_path}'", file=sys.stderr)
        return
    except Exception as e:
        print(f"Error reading input file {input_path}: {e}", file=sys.stderr)
        return

    try:
        # Parse the Python code into an Abstract Syntax Tree
        tree = ast.parse(file_content)
    except Exception as e:
        print(f"Error parsing Python code from {input_path}: {e}", file=sys.stderr)
        print("The file may be corrupt or not a valid Python script.", file=sys.stderr)
        return

    # Use the visitor to find the compressed string
    extractor = ZlibExtractor()
    extractor.visit(tree)

    if extractor.compressed_string and extractor.encoding:
        try:
            # The string from the AST is a regular Python string.
            # We must encode it back to bytes using 'latin-1'
            # to get the original compressed byte sequence.
            compressed_bytes = extractor.compressed_string.encode(extractor.encoding)
            
            # Decompress the bytes
            decompressed_data = zlib.decompress(compressed_bytes)
            
            # Write the decompressed (binary) data to the output file
            with open(output_path, 'wb') as f:
                f.write(decompressed_data)
            print(f"Successfully decompressed '{input_path}' to '{output_path}'.")
        
        except zlib.error as e:
            print(f"Error: Failed to decompress data. {e}", file=sys.stderr)
        except Exception as e:
            print(f"An error occurred during processing: {e}", file=sys.stderr)
    else:
        print("Error: Could not find the zlib-compressed string pattern in the file.", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="Decompress a Python file containing a zlib-compressed string encoded with 'L1'."
    )
    parser.add_argument(
        '--input', 
        required=True, 
        help="Path to the compressed input .py file (e.g., task001.py)."
    )
    parser.add_argument(
        '--output', 
        required=True, 
        help="Path to write the decompressed output file (e.g., task001_decompressed.py)."
    )
    
    args = parser.parse_args()
    
    decompress_file(args.input, args.output)

if __name__ == "__main__":
    main()
