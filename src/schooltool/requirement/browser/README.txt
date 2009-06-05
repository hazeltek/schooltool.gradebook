===========================
Requirements via the Web UI
===========================

This document presents the mangagement of requirements from the perspective
of the Web UI.

    >>> from zope.testbrowser.testing import Browser
    >>> browser = Browser()
    >>> browser.addHeader('Authorization', 'Basic manager:schooltool')

    >>> browser.handleErrors = False
    >>> browser.open('http://localhost/')


Requirement Management
----------------------

Requirements are accessed using the requirement namespace.  The namespace can
be used on anything that has been configured to implement IHaveRequirement 
First we will look at global requirements, which are attached to the
``SchoolToolApplication`` object.  From this screen we can add subrequirements.

    >>> browser.open('http://localhost/++requirement++')
    >>> 'Your School Sub Requirements' in browser.contents
    True

    >>> browser.getLink('New Requirement').click()
    >>> browser.getControl('Title').value = u'Citizenship'
    >>> browser.getControl('Add').click()

    >>> 'Citizenship' in browser.contents
    True

We can then navigate to this new requirement and edit it.

    >>> browser.getLink('Citizenship').click()
    >>> 'Citizenship Sub Requirements' in browser.contents
    True

    >>> browser.getLink('Edit Requirement').click()
    >>> browser.getControl('Title').value = u'Being a Good Citizen'
    >>> browser.getControl('Apply').click()
    >>> 'Being a Good Citizen Sub Requirements' in browser.contents
    True

If we create a sub requirement within this one, it will show up in the
top level requirement, because the page recurses down the requirement tree.

    >>> browser.getLink('New Requirement').click()
    >>> browser.getControl('Title').value = u'Be kind to your fellow students.'
    >>> browser.getControl('Add').click()

    >>> browser.open('http://localhost/++requirement++')
    >>> 'Be kind to your fellow students.' in browser.contents
    True

The view defaults to showing a depth of 3 recurssions.  If we want to show
only the ones directly under the top level, we can use the depth control.

    >>> browser.getControl('2').name
    'DEPTH'
    >>> browser.getControl('2').click()
    >>> browser.getControl('1').click()
    >>> 'Be kind to your fellow students.' not in browser.contents
    True


Score System Management
-----------------------

Score Systems can be created by the user to supplement the ones that are
already delivered with schooltool.  To do so, as manager, the user goes
to the 'Manage' tab and clicks on the 'Score Systems' link.

    >>> from schooltool.app.browser.ftests import setup
    >>> manager = setup.logIn('manager', 'schooltool')
    >>> manager.getLink('Manage').click()
    >>> manager.getLink('Score Systems').click()

We see the score systems that come with schooltool.

    >>> analyze.printQuery("id('content-body')/form//a", manager.contents)
    <a href="http://localhost/scoresystems/view.html?name=extended-letter-grade">Extended Letter Grade</a>
    <a href="http://localhost/scoresystems/view.html?name=letter-grade">Letter Grade</a>
    <a href="http://localhost/scoresystems/view.html?name=passfail">Pass/Fail</a>

To add a new score system, the user clicks 'Add Score System'.

    >>> manager.getLink('Add Score System').click()
    >>> base_url = manager.url + '?form-submitted'
    >>> cancel_url = base_url + '&CANCEL'
    >>> update_url = base_url + '&UPDATE_SUBMIT'
    >>> save_url = base_url + '&SAVE'

We'll send the form values necessary to add a score system called 'Good/Bad'.

    >>> url = save_url + '&title=Good/Bad&displayed1=G&value1=1&percent1=60'
    >>> url = url + '&displayed2=B&value2=0&percent2=0'
    >>> manager.open(url)

Now we see the two score systems in the list.

    >>> analyze.printQuery("id('content-body')/form//a", manager.contents)
    <a href="http://localhost/scoresystems/view.html?name=extended-letter-grade">Extended Letter Grade</a>
    <a href="http://localhost/scoresystems/view.html?name=goodbad">Good/Bad</a>
    <a href="http://localhost/scoresystems/view.html?name=letter-grade">Letter Grade</a>
    <a href="http://localhost/scoresystems/view.html?name=passfail">Pass/Fail</a>

Let's hide the 'Pass/Fail' one.

    >>> hide_url = manager.url + '?form-submitted&hide_passfail'
    >>> manager.open(hide_url)

Now we won't see it in the list.

    >>> analyze.printQuery("id('content-body')/form//a", manager.contents)
    <a href="http://localhost/scoresystems/view.html?name=extended-letter-grade">Extended Letter Grade</a>
    <a href="http://localhost/scoresystems/view.html?name=goodbad">Good/Bad</a>
    <a href="http://localhost/scoresystems/view.html?name=letter-grade">Letter Grade</a>

Let's click on 'Good/Bad' and test it's view.

    >>> manager.getLink('Good/Bad').click()
    >>> analyze.printQuery("id('content-body')/table//span", manager.contents)
    <span>G</span>
    <span>1</span>
    <span>60</span>
    <span>B</span>
    <span>0</span>
    <span>0</span>

