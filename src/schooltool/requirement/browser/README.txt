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
    <a href="http://localhost/scoresystems/extended-letter-grade">Extended Letter Grade</a>
    <a href="http://localhost/scoresystems/letter-grade">Letter Grade</a>
    <a href="http://localhost/scoresystems/passfail">Pass/Fail</a>

To add a new score system, the user clicks 'Add Score System'.

    >>> manager.getLink('Add Score System').click()
    >>> base_url = manager.url + '?form-submitted'
    >>> cancel_url = base_url + '&CANCEL'
    >>> update_url = base_url + '&UPDATE_SUBMIT'
    >>> save_url = base_url + '&SAVE'

We'll send the form values necessary to add a score system called 'Good/Bad'.

    >>> url = update_url + '&title=Good/Bad&displayed1=G&abbr1=&value1=1&percent1=60'
    >>> url = url + '&displayed2=B&abbr2=&value2=0&percent2=0'
    >>> url = url + '&minScore=G'
    >>> manager.open(url)

Now we see the new score system in the list.

    >>> analyze.printQuery("id('content-body')/form//a", manager.contents)
    <a href="http://localhost/scoresystems/extended-letter-grade">Extended Letter Grade</a>
    <a href="http://localhost/scoresystems/goodbad">Good/Bad</a>
    <a href="http://localhost/scoresystems/letter-grade">Letter Grade</a>
    <a href="http://localhost/scoresystems/passfail">Pass/Fail</a>

Let's hide the 'Pass/Fail' one.

    >>> hide_url = manager.url + '?form-submitted&hide_passfail'
    >>> manager.open(hide_url)

Now we won't see it in the list.

    >>> analyze.printQuery("id('content-body')/form//a", manager.contents)
    <a href="http://localhost/scoresystems/extended-letter-grade">Extended Letter Grade</a>
    <a href="http://localhost/scoresystems/goodbad">Good/Bad</a>
    <a href="http://localhost/scoresystems/letter-grade">Letter Grade</a>

Let's click on 'Good/Bad' and test it's view.

    >>> manager.getLink('Good/Bad').click()
    >>> analyze.printQuery("id('content-body')/table//span", manager.contents)
    <span>G</span>
    <span></span>
    <span>1</span>
    <span>60</span>
    <span>Yes</span>
    <span>B</span>
    <span></span>
    <span>0</span>
    <span>0</span>
    <span>No</span>

There's an 'OK' button that takes the user back to the score systems overview.

    >>> manager.getLink('OK').click()
    >>> manager.url
    'http://localhost/scoresystems'


Max passing score
-----------------

Some schools might want to create score systems that have a maximum passing
score rather than a minimum.

    >>> manager.getLink('Add Score System').click()

    >>> url = update_url + '&title=Max&displayed1=A&abbr1=&value1=4&percent1=75'
    >>> url = url + '&displayed2=B&abbr2=&value2=3&percent2=50'
    >>> url = url + '&displayed3=C&abbr3=&value3=2&percent3=25'
    >>> url = url + '&displayed4=D&abbr4=&value4=1&percent4=0'
    >>> url = url + '&minScore=C'
    >>> url = url + '&minMax=max'
    >>> manager.open(url)

When we view the max score system, we note that the passing scores are at the
bottom, 'C' being the largest passing score.

    >>> manager.getLink('Max').click()
    >>> analyze.printQuery("id('content-body')/table//span", manager.contents)
    <span>A</span>
    <span></span>
    <span>4</span>
    <span>75</span>
    <span>No</span>
    <span>B</span>
    <span></span>
    <span>3</span>
    <span>50</span>
    <span>No</span>
    <span>C</span>
    <span></span>
    <span>2</span>
    <span>25</span>
    <span>Yes</span>
    <span>D</span>
    <span></span>
    <span>1</span>
    <span>0</span>
    <span>Yes</span>

