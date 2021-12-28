import collections
import math

from sly import Parser
from lex.lexer import MainLexer


Variable = collections.namedtuple('Variable', ['name'])
Expression = collections.namedtuple('Expression', ['operation', 'arguments'])
Statement = collections.namedtuple('Statement', ['operation', 'arguments'])

class MainParser(Parser):
    tokens = MainLexer.tokens

    precedence = (
        ('nonassoc', IF, THEN),
        ('left', EQ),
        ('nonassoc', ELSE),
    )

    def __init__(self):
        self.ids = { }

    @_('LPAREN ID EQ ID RPAREN',
        'LPAREN ID LE ID RPAREN',
        'LPAREN ID LT ID RPAREN',
        'LPAREN ID GE ID RPAREN',
        'LPAREN ID GT ID RPAREN'
    )
    def statement(self, p):
        if p[2] == '==':
            return p.ID0 == p.ID1
        if p[2] == '<=':
            return p.ID0 <= p.ID1
        if p[2] == '<':
            return p.ID0 < p.ID1
        if p[2] == '>=':
            return p.ID0 >= p.ID1
        if p[2] == '>':
            return p.ID0 > p.ID1

    @_('statement')
    def statements(self, parsed):
        if parsed.statement:
            return parsed.statement


    @_('IF LPAREN expr RPAREN THEN statements')
    def statement(self, parsed):
        if parsed.expr:
            return parsed.statements

    @_('''IF LPAREN expr RPAREN
            THEN statements 
        ELSE statement''')
    def statement(self, parsed):
        if parsed.expr == True:
            return parsed.statements
        else:
            return parsed.statement

    @_('PRINT LPAREN expr RPAREN')
    def statement(self, p):
        return p[2]

    @_('ID PLUSASSIGN expr')
    def statement(self, p):
        self.ids[p.ID] += p.expr
        return self.ids[p.ID]
    
    @_('ID ASSIGN expr')
    def statement(self, p):
        self.ids[p.ID] = p.expr
        return p.expr
        
    @_('expr PLUS term',
        'expr MINUS term')
    def expr(self, p):
        if p[0] == '+':
            return p.expr + p.term
        if p[0] == '-':
            return p.expr - p.term

    @_('term')
    def expr(self, p):
        return p.term
    
    @_('expr')
    def statement(self, p):
        return p.expr

    @_('term TIMES factor',
    'term DIVIDE factor')
    def term(self, p):
        if p[1] == '*':
            return p.term * p.factor
        if p[1] == '/':
            return p.term / p.factor

    @_('factor')
    def term(self, p):
        return p.factor

    @_('NUMBER')
    def factor(self, p):
        return p.NUMBER

    @_('ID GT ID')
    def expr(self, p):
        return p.ID0 > p.ID1

    @_('LPAREN expr RPAREN')
    def factor(self, p):
        return p.expr

    @_(
        'NUMBER',
        'STRING',
    )
    def expr(self, parsed):
        return parsed[0]

    @_('ID')
    def expr(self, p):
        try:
            return self.ids[p.ID]
        except LookupError:
            print('Undefined name {}'.format(p))
            return 0

    @_('EXIT')
    def expr(self, p):
        print("EXIT")
        exit()