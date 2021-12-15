from sly import Parser
from lexer import CalcLexer

class CalcParser(Parser):
    # Get the token list from the lexer (required)
    tokens = CalcLexer.tokens

    def __init__(self):
        self.ids = { }
    # Grammar rules and actions

    @_('PRINT LPAREN expr RPAREN')
    def statement(self, p):
        print(p[2])
        
    @_('IF LPAREN ID EQ ID RPAREN')
    def statement(self, p):
        return p.ID0 == p.ID1

    @_('IF LPAREN ID LE ID RPAREN')
    def statement(self, p):
        return p.ID0 <= p.ID1

    @_('IF LPAREN ID LT ID RPAREN')
    def statement(self, p):
        return p.ID0 < p.ID1

    @_('IF LPAREN ID GE ID RPAREN')
    def statement(self, p):
        return p.ID0 >= p.ID1

    @_('IF LPAREN ID GT ID RPAREN')
    def statement(self, p):
        return p.ID0 > p.ID1

    @_('ID PLUSASSIGN expr')
    def statement(self, p):
        self.ids[p.ID] += p.expr
        return p.expr
    
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

    @_('ID')
    def expr(self, p):
        try:
            return self.ids[p.ID]
        except LookupError:
            if p[0] == 'EXIT':
                print("EXIT")
                exit()
            else:
                print(f'Undefined name {p.ID!r}')
                return 0
            
