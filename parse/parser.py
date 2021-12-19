import collections
import math

from sly import Parser
from lex.lexer import MainLexer


Variable = collections.namedtuple('Variable', ['name'])
Expression = collections.namedtuple('Expression', ['operation', 'arguments'])
Statement = collections.namedtuple('Statement', ['operation', 'arguments'])

class MainParser(Parser):
    tokens = MainLexer.tokens
    #start = "bmba"
    precedence = (
        ('nonassoc', IF, THEN),
        ('left', EQ),
        ('nonassoc', ELSE),
    )

    def __init__(self):
        self.ids = { }

    @_('statement')
    def statements(self, parsed):
        if parsed.statement:
            return parsed.statement

    @_('statements COLON statement')
    def statements(self, parsed):
        parsed.statements.append(parsed.statement)
        return parsed.statements

    @_(
        'statements COLON empty',
        'empty COLON statements',
    )
    def statements(self, parsed):
        return parsed.statements

    @_('')
    def empty(self, parsed):
        pass

    @_('IF expr THEN statements')
    def statement(self, parsed):
        if parsed.expr:
            return parsed.statements

    @_('IF expr THEN statements ELSE statement')
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
        
    @_('expr PLUS term')
    def expr(self, p):
        return p.expr + p.term

    @_('expr MINUS term')
    def expr(self, p):
        return p.expr - p.term

    @_('term')
    def expr(self, p):
        return p.term
    
    @_('expr')
    def statement(self, p):
        return p.expr

    @_('term TIMES factor')
    def term(self, p):
        return p.term * p.factor

    @_('term DIVIDE factor')
    def term(self, p):
        return p.term / p.factor

    @_('factor')
    def term(self, p):
        return p.factor

    @_('NUMBER')
    def factor(self, p):
        return p.NUMBER

    @_('LPAREN expr RPAREN')
    def factor(self, p):
        return p.expr

    @_("START_L NUMBER END_L")
    def expr(self, p):
        return p.NUMBER

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
            if p[0] == 'EXIT':
                print("EXIT")
                exit()
            else:
                print('Undefined name {}'.format(p))
                return 0
            
