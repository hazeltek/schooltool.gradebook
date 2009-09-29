# Make a package

def registerTestSetup():
    from schooltool.testing import registry

    def addDefaultCategories(app):
        from schooltool.gradebook.gradebook import GradebookInit
        gb_init = GradebookInit(app)
        gb_init()
    registry.register('DefaultCategories', addDefaultCategories)

registerTestSetup()
del registerTestSetup

def makeDecimalARock():
    # XXX this is insecure
    from decimal import Decimal
    from zope.security.checker import NoProxy
    import zope.security
    zope.security.checker.BasicTypes[Decimal] = NoProxy

makeDecimalARock()
del makeDecimalARock

def sliceString(source, start, end=None, startIndex=0, endIndex=0,
                includeEnd=False):
    index = -1 * len(start)
    while startIndex >= 0:
        index += len(start)
        index = source[index:].find(start)
        if index < 0:
            index = 0
            break
        startIndex -= 1
    if end is None:
        last = len(source)
    else:
        last = index - len(end)
        while endIndex >= 0:
            last += len(end)
            next = source[last:].find(end)
            if next < 0:
                last = len(source)
                break
            else:
                last += next
            endIndex -= 1
        if last < len(source) and includeEnd:
            last += len(end)
    return source[index:last]

