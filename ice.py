from parser import CalcParser
from lexer import CalcLexer
import fire 

if __name__ == '__main__':
    lexer = CalcLexer()
    parser = CalcParser()

    while True:
        def run(filen=None):
            if filen is None:
                text = input('ice: ')
                result = parser.parse(lexer.tokenize(text))
                print(result)
            else:
                with open('{}'.format(filen), 'r') as text:
                    for line in text:
                        result = parser.parse(lexer.tokenize(line))
                        print(result)
        try:
            fire.Fire(run)
        except EOFError:
            break
        except KeyboardInterrupt:
            print("exit program")
            exit()