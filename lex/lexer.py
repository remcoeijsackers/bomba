from sly import Lexer

class MainLexer(Lexer):
    # Set of token names.   This is always required
    tokens = { NUMBER, ID, WHILE, IF, ELSE, PRINT,
               PLUS, MINUS, TIMES, DIVIDE, PLUSASSIGN, ASSIGN,
               EQ, LT, LE, GT, GE, NE, LPAREN, RPAREN, LBRACK, RBRACK, START_L, END_L }


    literals = { '(', ')', '{', '}', ';' , '[', ']'}

    # String containing ignored characters
    ignore = ' \t'

    # Regular expression rules for tokens
    PLUS    = r'\+'
    MINUS   = r'-'
    TIMES   = r'\*'
    DIVIDE  = r'/'
    PLUSASSIGN  = r'p='
    EQ      = r'=='
    ASSIGN  = r'='
    LE      = r'<='
    LT      = r'<'
    GE      = r'>='
    GT      = r'>'
    NE      = r'!='
    LPAREN  = r'\('
    RPAREN  = r'\)'
    LBRACK = r'\['
    RBRACK = r'\]'
    START_L = r'startl'
    END_L = r'endl'

    
    @_(r'\d+')
    def NUMBER(self, t):
        t.value = int(t.value)
        return t

    # Identifiers and keywords
    ID = r'[a-zA-Z_][a-zA-Z0-9_]*'
    ID['if'] = IF
    ID['else'] = ELSE
    ID['while'] = WHILE
    ID['print'] = PRINT
    #ID['startl'] = START_L
    #ID['endl'] = END_L

    ignore_comment = r'\#.*'

    # Line number tracking
    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += t.value.count('\n')
    
    @_(r"[ \t\n]+")
    def ignore_whitespace(self, t):
        self.lineno += t.value.count("\n")

    def error(self, t):
        print('Line %d: Bad character %r' % (self.lineno, t.value[0]))
        self.index += 1
