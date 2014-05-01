import schooltool.common
from zope.i18nmessageid import MessageFactory
GradebookMessage = MessageFactory("schooltool.gradebook")

def registerTestSetup():
    from schooltool.testing import registry

    def addDefaultCategories(app):
        from schooltool.gradebook.gradebook import GradebookInit
        gb_init = GradebookInit(app)
        gb_init()
    registry.register('DefaultCategories', addDefaultCategories)

registerTestSetup()
del registerTestSetup

schooltool.common.register_lauchpad_project(__package__, 'schooltool.gradebook')
