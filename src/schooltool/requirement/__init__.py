from zope.i18nmessageid import MessageFactory
import schooltool.common

RequirementMessage = MessageFactory("schooltool.gradebook")

def makeDecimalARock():
    # XXX this is insecure
    from decimal import Decimal
    from zope.security.checker import NoProxy
    import zope.security
    zope.security.checker.BasicTypes[Decimal] = NoProxy

makeDecimalARock()
del makeDecimalARock

schooltool.common.register_lauchpad_project(__package__, 'schooltool.gradebook')
