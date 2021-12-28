import collections
import math

from sly import Lexer

Variable = collections.namedtuple('Variable', ['name'])
Expression = collections.namedtuple('Expression', ['operation', 'arguments'])
Statement = collections.namedtuple('Statement', ['operation', 'arguments'])


class MainLexer(Lexer):
    # Set of token names.   This is always required
    tokens = { NUMBER, ID, WHILE, IF, THEN, ELSE, PRINT,
               PLUS, MINUS, TIMES, DIVIDE, PLUSASSIGN, ASSIGN,
               EQ, LT, LE, GT, GE, NE, LPAREN, RPAREN, LBRACK, RBRACK, START_L, END_L, COLON, STRING, NOOTP, EXIT }


    literals = { '(', ')', '{', '}', ';' , '[', ']'}

    # Regular expression rules for tokens
    COLON = r':'
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
    IF = r'IF'
    THEN = r'THEN'
    PRINT = r'PRINT'
    ELSE = r'ELSE'
    NOOTP = r'NOOTP'
    EXIT = r'EXIT'
    #COMMENT = r"(?:#|').*"

    
    @_(r'\d+')
    def NUMBER(self, t):
        t.value = int(t.value)
        return t

    @_(r'"[^"]*"?')
    def STRING(self, token):
        token.value = token.value[1:]

        if token.value.endswith('"'):
            token.value = token.value[:-1]

        return token
        
    # Identifiers and keywords
    ID = r'[a-zA-Z_][a-zA-Z0-9_]*'

    # Line number tracking
    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += len(t.value)
    
    @_(r"[ \t\n]+")
    def ignore_whitespace(self, t):
        self.lineno += t.value.count("\n")

    @_(r'\#.*')
    def ignore_comment(self, t):
        self.lineno += t.value.count("\n")

    def error(self, t):
        print('Line %d: Bad character %r' % (self.lineno, t.value[0]))
        self.index += 1
