"""
    Credit: https://github.com/Netflix-Skunkworks/policyuniverse
    Patrick Kelley <patrick@netflix.com>

"""

from .statement import Statement
import logging


logger = logging.getLogger(__name__)


class Policy(object):
    def __init__(self, policy):
        self.policy = policy
        self.statements = []

        statement_structure = self.policy.get("Statement", [])
        if not isinstance(statement_structure, list):
            statement_structure = [statement_structure]

        for statement in statement_structure:
            self.statements.append(Statement(statement))

    @property
    def principals(self):
        principals = set()
        for statement in self.statements:
            principals = principals.union(statement.principals)
        return principals

    def whos_allowed(self):
        allowed = set()
        for statement in self.statements:
            if statement.effect == "Allow":
                allowed = allowed.union(statement.whos_allowed())
        return allowed

    def evaluate(self, context):
        logger.debug("context: ", context)
        logger.debug("statements: ", self.statements)

        try:
            allow = False
            for statement in self.statements:
                logger.debug("statement: ", statement.statement)
                passed = statement.evaluate(context)
                logger.debug("passed: ", passed)
                if passed == True:  # has access according to this statement
                    allow = True
                elif passed == False:  # denied, end and return false
                    return False
                elif passed == None:  # statement has no effect
                    continue

            return allow
        except Exception as err:
            logger.debug("------------- Error in evaluate policy:\n ", str(err))
            return False