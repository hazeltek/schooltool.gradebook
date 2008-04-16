=============
The Gradebook
=============

There are many tasks that are involved in setting up and using a
gradebook. The first task the administrator has to complete during the
SchoolTool setup is the configuration of the categories. So let's log in as a
manager:

   >>> from schooltool.app.browser.ftests import setup
   >>> manager = setup.logInManager()


Initial School Setup
--------------------

We will use the 'Manage' tab to find the 'Activity Categories' link to set up
the categories:

    >>> manager.getLink('Manage').click()
    >>> manager.getLink('Activity Categories').click()

As you can see, there are already several categories pre-defined. Oftentimes,
those categories do not work for a school. Either you do not need some and/or
others are missing. So let's start by deleting a couple of categories:

    >>> 'essay' in manager.contents
    True
    >>> 'journal' in manager.contents
    True

    >>> manager.getControl(name='field.categories:list').value = [
    ...     'essay', 'journal', 'homework', 'presentation']
    >>> manager.getControl('Remove').click()

    >>> 'essay' in manager.contents
    False
    >>> 'journal' in manager.contents
    False

Next, we add a new category:

    >>> 'Lab Report' in manager.contents
    False

    >>> manager.getControl('New Category').value = 'Lab Report'
    >>> manager.getControl('Add').click()

    >>> 'Lab Report' in manager.contents
    True

We can also change the default category:

    >>> manager.getControl('Default Category').value
    ['assignment']

    >>> manager.getControl('Default Category').value = ['exam']
    >>> manager.getControl('Change').click()

    >>> manager.getControl('Default Category').value
    ['exam']

Next the administrator defines the courses that are available in the school.

    >>> manager.getLink('Manage').click()
    >>> manager.getLink('Courses').click()
    >>> manager.getLink('New Course').click()
    >>> manager.getControl('Title').value = 'Physics I'
    >>> manager.getControl('Add').click()
    >>> manager.getLink('Physics I').click()

This completes the initial school setup.


Term Setup
----------

Every term, the administrators of a school are going to setup sections. So
let's add a section for our course:

    >>> from schooltool.app.browser.ftests import setup
    >>> setup.addSection('Physics I')

But what would a section be without some students and a teacher?

    >>> from schooltool.app.browser.ftests.setup import addPerson
    >>> addPerson('Paul Cardune', 'paul', 'pwd')
    >>> addPerson('Tom Hoffman', 'tom', 'pwd')
    >>> addPerson('Claudia Richter', 'claudia', 'pwd')
    >>> addPerson('Stephan Richter', 'stephan', 'pwd')

Now we can add those people to the section:

    >>> manager.getLink('Manage').click()
    >>> manager.getLink('Courses').click()
    >>> manager.getLink('Physics I').click()
    >>> manager.getLink('(1)').click()

    >>> manager.getLink('edit individuals').click()
    >>> manager.getControl('Paul Cardune').click()
    >>> manager.getControl('Tom Hoffman').click()
    >>> manager.getControl('Claudia Richter').click()
    >>> manager.getControl('Add').click()
    >>> manager.getControl('OK').click()

    >>> 'Paul Cardune' in manager.contents
    True

    >>> manager.getLink('edit instructors').click()
    >>> manager.getControl('Stephan Richter').click()
    >>> manager.getControl('Add').click()
    >>> manager.getControl('OK').click()


Instructor should be automatically capable of manipulating activities
and other section data.

Gradebook Management
--------------------

Once the term started, the instructor of the section will start by
creating two worksheets, one for each week in our two week section.
To set up the activities, we will start by clicking the 'Gradebook'
tab.  As Stephan is only a teacher at this point and does not
attend any classes himself (we will change that later), he will be
taken directly to the gradebook view for the first section in the
list of sections he teachers.  In this case, he only teachers the
one section.

    >>> stephan = setup.logIn('stephan', 'pwd')
    >>> stephan.getLink('Gradebook').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...Physics I (1)...
    ...View Final Grades...
    ...Claudia...
    ...Paul...
    ...Tom...

Now we can use the 'Activities' link to get us to the view for
adding activities to the section:

    >>> stephan.getLink('Activities').click()

    >>> stephan.getLink('New Worksheet').click()
    >>> stephan.getControl('Title').value = 'Week 1'
    >>> stephan.getControl('Add').click()
    >>> 'Week 1' in stephan.contents
    True

    >>> stephan.getLink('New Worksheet').click()
    >>> stephan.getControl('Title').value = 'Week 2'
    >>> stephan.getControl('Add').click()
    >>> 'Week 2' in stephan.contents
    True

Note that 'Week 1' is the currently selected worksheet.

    >>> '<option value="Week 1" selected="selected">Week 1</option>' in \
    ...  stephan.contents
    True

Now, let's add some activities to it.  First we'll verify that the activities
add view has the right list of existing score systems.

    >>> stephan.getLink('New Activity').click()
    >>> print analyze.queryHTML('id("field.scoresystem.existing")', stephan.contents)[0]
    <select id="field.scoresystem.existing" name="field.scoresystem.existing" size="1">
      <option selected="selected" value="">(no value)</option>
      <option value="100 Points">100 Points</option>
      <option value="Extended Letter Grade">Extended Letter Grade</option>
      <option value="Letter Grade">Letter Grade</option>
      <option value="Pass/Fail">Pass/Fail</option>
      <option value="Percent">Percent</option>
    </select>

Now we'll test what happens when we try to add the activity without filling in
all of the required fields.  The only fields that are required and could
potentially be left out by the user are title and scoresystem.

    >>> stephan.getControl('Add').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...There are <strong>2</strong> input errors...
    ...A brief title of the requirement...
    ...Required input is missing...
    ...The activity scoresystem...
    ...Required input is missing...

Now we will fill in all of the required fields, first creating an activity that
uses an existing score system.  We'll note that the new activity appears in
the activities overview after successfully being added.

    >>> stephan.getControl('Title').value = 'HW 1'
    >>> stephan.getControl('Description').value = 'Homework 1'
    >>> stephan.getControl('Category').value = ['assignment']
    >>> stephan.getControl(
    ...     name='field.scoresystem.existing').value = ['100 Points']
    >>> stephan.getControl('Add').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...New Worksheet...
    ...New Activity...
    ...HW 1...

We'll add a second activity.

    >>> stephan.getLink('New Activity').click()
    >>> stephan.getControl('Title').value = 'Quiz'
    >>> stephan.getControl('Description').value = 'Week 1 Pop Quiz'
    >>> stephan.getControl('Category').value = ['exam']
    >>> stephan.getControl(
    ...     name='field.scoresystem.existing').value = ['100 Points']
    >>> stephan.getControl('Add').click()
    >>> 'Quiz' in stephan.contents
    True

But, oh, we really did not want to make Homework 1 out of a hundred points,
but only out of 50. So let's edit it:

    >>> stephan.getLink('HW 1').click()
    >>> stephan.getControl('Custom score system').click()
    >>> stephan.getControl('Maximum').value = '50'
    >>> stephan.getControl('Apply').click()

Now let's change the current workskeet to 'Week 2'.

    >>> stephan.open(stephan.url+'?form-submitted=&currentWorksheet=Week%202')
    >>> '<option value="Week 2" selected="selected">Week 2</option>' in \
    ...  stephan.contents
    True

Now we'll add some activities to it.

    >>> stephan.getLink('New Activity').click()
    >>> stephan.getControl('Title').value = 'HW 2'
    >>> stephan.getControl('Description').value = 'Homework 2'
    >>> stephan.getControl('Category').value = ['assignment']
    >>> stephan.getControl(
    ...     name='field.scoresystem.existing').value = ['100 Points']
    >>> stephan.getControl('Add').click()
    >>> 'HW 2' in stephan.contents
    True

    >>> stephan.getLink('New Activity').click()
    >>> stephan.getControl('Title').value = 'Final'
    >>> stephan.getControl('Description').value = 'Final Exam'
    >>> stephan.getControl('Category').value = ['exam']
    >>> stephan.getControl(
    ...     name='field.scoresystem.existing').value = ['100 Points']
    >>> stephan.getControl('Add').click()
    >>> 'Final' in stephan.contents
    True

Now that we have all our activities setup, we would like to rearrange their
order more logically. The final in week 2 should really be at the end of the
list. In the browser you should usually just select the new position and some
Javascript would submit the form. Since Javascript is not working in the
tests, we submit, the form manually:

    >>> stephan.open(stephan.url+'?form-submitted=&pos.Activity-3=3')
    >>> stephan.contents.find('HW 2') \
    ...     < stephan.contents.find('Final')
    True

You can also delete activities that you have created:

    >>> stephan.getLink('New Activity').click()
    >>> stephan.getControl('Title').value = 'HW 3'
    >>> stephan.getControl('Description').value = 'Homework 3'
    >>> stephan.getControl('Category').value = ['assignment']
    >>> stephan.getControl(
    ...     name='field.scoresystem.existing').value = ['100 Points']
    >>> stephan.getControl('Add').click()
    >>> 'HW 3' in stephan.contents
    True

    >>> stephan.getControl(name='delete:list').value = ['Activity-3']
    >>> stephan.getControl('Delete').click()
    >>> 'HW 3' in stephan.contents
    False

Fianlly, let's change the current workskeet back to 'Week 1'.  This setting
of current worksheet will be in effect for the gradebook as well.

    >>> stephan.open(stephan.url+'?form-submitted=&currentWorksheet=Week%201')
    >>> '<option value="Week 1" selected="selected">Week 1</option>' in \
    ...  stephan.contents
    True


Grading
-------

Now that we have both students and activities, we can enter the gradebook.
We'll use the link registered for IActivities that gets us there.  This
link, called 'Return to Gradebook' is different than the 'Gradebook' tab
itself in that it takes the user back to the gradebook for the same section
that the activities view referenced.

    >>> stephan.getLink('Return to Gradebook').click()

The initial gradebook screen is a simple spreadsheet. In order to prevent
accidental score submission, we do not allow to enter grades in this
table. Instead you select a row (student), column (activity) or cell (student,
activity) to enter the scores.

Since we just loaded up the gradebook for the first time, the current worksheet
will be the first one, Week 1.  Only the activities for that worksheet should
appear.

    >>> 'HW 1' in stephan.contents and 'Quiz' in stephan.contents
    True
    >>> 'HW 2' in stephan.contents or 'Final</a>' in stephan.contents
    False



Entering Scores for a Row (Student)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's say we want to enter the grades for Claudia. All we do is to simply
click on her name:

    >>> stephan.getLink('Claudia Richter').click()

Now we just enter the grades:

    >>> stephan.getControl('HW 1').value = u'-1'
    >>> stephan.getControl('Quiz').value = u'56'
    >>> stephan.getControl('Update').click()

But since I entered an invlaid value for Homework 1, we get an error message:

    >>> 'The grade -1 for activity HW 1 is not valid.' in stephan.contents
    True

Also note that all the other entered values should be retained:

    >>> 'value="-1"' in stephan.contents
    True
    >>> 'value="56"' in stephan.contents
    True
    >>> stephan.getControl('HW 1').value = u'36'
    >>> stephan.getControl('Update').click()

The screen will return to the grade overview, where the grades are no visible:

    >>> '>36<' in stephan.contents
    True
    >>> '>56<' in stephan.contents
    True

Also, there will be an average grade displayed that the teacher can use to
formulate a final grade.

    >>> '>61%<' in stephan.contents
    True

Now let's enter again and change a grade:

    >>> stephan.getLink('Claudia Richter').click()
    >>> stephan.getControl('HW 1').value = u'46'
    >>> stephan.getControl('Update').click()
    >>> '>46<' in stephan.contents
    True

When you want to delete an evaluation altogether, simply blank the value:

    >>> stephan.getLink('Claudia Richter').click()
    >>> stephan.getControl('HW 1').value = u''
    >>> stephan.getControl('Update').click()
    >>> '>46<' in stephan.contents
    False

Of course, you can also abort the grading.

    >>> stephan.getLink('Claudia Richter').click()
    >>> stephan.getControl('Cancel').click()
    >>> stephan.url
    'http://localhost/sections/1/gradebook/index.html'

Let's put Claudia's grade back in:

    >>> stephan.getLink('Claudia Richter').click()
    >>> stephan.getControl('HW 1').value = u'36'
    >>> stephan.getControl('Update').click()
    >>> '>36<' in stephan.contents
    True


Entering Scores for a Column (Activity)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's say we want to enter the grades for Homework 1. All we do is to simply
click on the activity's name:

    >>> stephan.getLink('HW 1').click()

Now we just enter the grades. Since Claudia has already a grade, we only need
to grade Paul and Tom:

    >>> stephan.getControl('Paul Cardune').value = u'-1'
    >>> stephan.getControl('Tom Hoffman').value = u'42'
    >>> stephan.getControl('Update').click()

Again, we entered an invalid value, this time for Paul:

    >>> 'The grade -1 for Paul Cardune is not valid.' in stephan.contents
    True

Also note that all the other entered values should be retained:

    >>> 'value="-1"' in stephan.contents
    True
    >>> 'value="42"' in stephan.contents
    True
    >>> 'value="36"' in stephan.contents
    True
    >>> stephan.getControl('Paul Cardune').value = u'40'
    >>> stephan.getControl('Update').click()

The screen will return to the grade overview, where the grades are now
visible:

    >>> '>40<' in stephan.contents
    True
    >>> '>42<' in stephan.contents
    True
    >>> '>36<' in stephan.contents
    True

Now let's enter again and change a grade:

    >>> stephan.getLink('HW 1').click()
    >>> stephan.getControl('Claudia Richter').value = u'48'
    >>> stephan.getControl('Update').click()
    >>> '>48<' in stephan.contents
    True

When you want to delete an evaluation altogether, simply blank the value:

    >>> stephan.getLink('HW 1').click()
    >>> stephan.getControl('Claudia Richter').value = u''
    >>> stephan.getControl('Update').click()
    >>> '>98<' in stephan.contents
    False

Of course, you can also abort the grading.

    >>> stephan.getLink('HW 1').click()
    >>> stephan.getControl('Cancel').click()
    >>> stephan.url
    'http://localhost/sections/1/gradebook/index.html'

Let's enter some grades for the second worksheet, 'Week 2', so that we have
some interesting numbers for the final grades view.

    >>> stephan.open(stephan.url+'?form-submitted=&currentWorksheet=Week%202')
    >>> stephan.getLink('HW 2').click()
    >>> stephan.getControl('Paul Cardune').value = u'90'
    >>> stephan.getControl('Tom Hoffman').value = u'72'
    >>> stephan.getControl('Claudia Richter').value = u'42'
    >>> stephan.getControl('Update').click()

We'll set the current worksheet back to week 1 for the rest of the tests.

    >>> stephan.open(stephan.url+'?form-submitted=&currentWorksheet=Week%201')


Entering Scores for a Cell (Student, Activity)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When you click directly on the grade, you can also edit it. Let's day that we
want to modify Claudia's Quiz grade. Until now she had a 56:

    >>> stephan.getLink('56').click()

The screen that opens gives you several pieces of information, such as the
student's name,

    >>> 'Claudia Richter' in stephan.contents
    True

the activity name,

    >>> 'Quiz' in stephan.contents
    True

the (due) date of the activity,

    # Cannot show the value because it is variable
    >>> '(Due) Date' in stephan.contents
    True

the last modification date,

    # Cannot show the value because it is variable
    >>> 'Modification Date' in stephan.contents
    True

and the maximum score:

    >>> '100' in stephan.contents
    True

This for also allows you to delete the evaluation, which is sometimes
necessary:

    >>> stephan.getControl('Grade').value
    '56'
    >>> stephan.getControl('Delete').click()
    >>> stephan.getControl('Grade').value
    ''

Now let's enter a new grade:

    >>> stephan.getControl('Grade').value = '86'
    >>> stephan.getControl('Update').click()
    >>> stephan.url
    'http://localhost/sections/1/gradebook/index.html'
    >>> '>86<' in stephan.contents
    True

Of course, you can also cancel actions:

    >>> stephan.getLink('86').click()
    >>> stephan.getControl('Grade').value = '66'
    >>> stephan.getControl('Cancel').click()
    >>> stephan.url
    'http://localhost/sections/1/gradebook/index.html'
    >>> '>86<' in stephan.contents
    True


Sorting
~~~~~~~

Another feature of the gradebook is the ability to sort each column in a
descending and ascending fashion. By default the student's name is sorted
alphabetically:

    >>> stephan.contents.find('Claudia') \
    ...     < stephan.contents.find('Paul') \
    ...     < stephan.contents.find('Tom')
    True

Then we want to sort by grade in Homework 1, so we should have:

    >>> import re
    >>> url = re.compile('.*sort_by=-?[0-9]+')
    >>> stephan.getLink(url=url).click()
    >>> stephan.contents.find('Paul') \
    ...     < stephan.contents.find('Tom') \
    ...     < stephan.contents.find('Claudia')
    True

Clicking it again, reverses the order:

    >>> stephan.getLink(url=url).click()
    >>> stephan.contents.find('Claudia') \
    ...     < stephan.contents.find('Tom') \
    ...     < stephan.contents.find('Paul')
    True


Final Grades
------------

Teachers will want a calculated final grade for each student in the section.
The view for for this will present the user with a table of students with
the average for each worksheet, the final calulated grade, an adjusted final
grade which equal the calculated final grade unless they have entered an
adjustment.  At first we will have no adjustments entered.

    >>> url = 'http://localhost/sections/1/gradebook/final.html'
    >>> stephan.open(url)
    >>> print stephan.contents
    <BLANKLINE>
    ...Claudia Richter...
    ...86</td>...
    ...42</td>...
    ...C</td>...
    ...C</td>...
    ...Paul Cardune...
    ...80</td>...
    ...90</td>...
    ...A</td>...
    ...A</td>...
    ...Tom Hoffman...
    ...84</td>...
    ...72</td>...
    ...B</td>...
    ...B</td>...

Now, let's adjust Claudia's grade to be a B becuase we like her so much.

    >>> stephan.open(url + '?adj_claudia=B&reason_claudia=because')
    >>> print stephan.contents
    <BLANKLINE>
    ...Claudia Richter...
    ...86</td>...
    ...42</td>...
    ...C</td>...
    ...B</td>...
    ...value="B"...
    ...value="because"...
    ...Paul Cardune...
    ...80</td>...
    ...90</td>...
    ...A</td>...
    ...A</td>...
    ...Tom Hoffman...
    ...84</td>...
    ...72</td>...
    ...B</td>...
    ...B</td>...

Invalid grades will result in an error message, and the original value and
reason will appear in the view in its place.

    >>> stephan.open(url + '?adj_claudia=F&reason_claudia=failure')
    >>> print stephan.contents
    <BLANKLINE>
    ...Adjustment final grade 'F' is not a valid grade...
    ...Claudia Richter...
    ...86</td>...
    ...42</td>...
    ...C</td>...
    ...B</td>...
    ...value="B"...
    ...value="because"...


My Grades
---------

Students should also be able to view their grades (not change them), so there's
a view for the student to see them.  Let's log in as Claudia and go to her grades
for the section.  It will come up with Week 1 as the current worksheet,  As
Claudia is only a student and only attends the one section, the 'Gradebook' tab
will take her directly to her grades for that section.

    >>> claudia = setup.logIn('claudia', 'pwd')
    >>> claudia.getLink('Gradebook').click()
    >>> claudia.url
    'http://localhost/sections/1/mygrades'
    >>> 'HW 1' in claudia.contents and 'Quiz' in claudia.contents
    True
    >>> 'HW 2' in claudia.contents or 'Final' in claudia.contents
    False
    >>> claudia.contents.find('Current Grade: 86%') \
    ...     < claudia.contents.find('HW 1') \
    ...     < claudia.contents.find('Quiz') \
    ...     < claudia.contents.find('86/100')
    True


Gradebook Startup View
----------------------

Now that we've tested both the teacher's gradebook and the student's mygrades
views, we'll want to more thoroughly test the view that get's launched when
the user clicks on the 'Gradebook' tab.  Up until now, the startup view has 
automatically redirected both the teacher and the student to the gradebook and
mygrades views respectively.  But what if the user neither attends or teachers
any classes, like a site manager, or if the user both teachers AND attends
classes?  We will test both of these scenarios.

First, the manager doesn't participate in any classes, so we'll give him a
simple message when he clicks on the 'Gradebook' tab.

    >>> manager.getLink('Gradebook').click()
    >>> print manager.contents
    <BLANKLINE>
    ...You do not teach or attend any classes...

In order to test the second scenario, we will have to create a second section
that has Stephan, teacher of the first Physics I section (1), attending a
second section rather than teaching.

    >>> setup.addSection('Physics I')
    >>> manager.getLink('Manage').click()
    >>> manager.getLink('Courses').click()
    >>> manager.getLink('Physics I').click()
    >>> manager.getLink('(2)').click()

    >>> manager.getLink('edit individuals').click()
    >>> manager.getControl('Stephan Richter').click()
    >>> manager.getControl('Add').click()
    >>> manager.getControl('OK').click()

    >>> manager.getLink('edit instructors').click()
    >>> manager.getControl('Tom Hoffman').click()
    >>> manager.getControl('Add').click()
    >>> manager.getControl('OK').click()

    >>> print manager.contents
    <BLANKLINE>
    ...Instructors...
    ...Tom Hoffman...
    ...Students...
    ...Stephan Richter...
 
 Now, when Stephan clicks on the 'Gradebook' tab, he will get a startup view
 that allows him to go to either his gradebook or his mygrades views.
 
    >>> stephan.getLink('Gradebook').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...Classes you teach...
    ...Classes you attend...

    >>> stephan.getLink('Classes you teach').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...Physics I (1)...
    ...View Final Grades...

    >>> stephan.getLink('Gradebook').click()
    >>> stephan.getLink('Classes you attend').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...Physics I (2)...
    ...Nothing Graded...


Gradebook Security
------------------

It was desirable to move the security tests out of schooltool and into the
schooltool.gradebook package where they belong, so here is where they will
be.

The first test will be for the unauthenticated user.  They should not be able
to see a gradebook and certainly don't have a mygrades view.

    >>> from zope.testbrowser.testing import Browser
    >>> unauth = Browser()
    >>> unauth.handleErrors = False
    >>> unauth.open('http://localhost/sections/1/gradebook')
    Traceback (most recent call last):
    ...
    Unauthorized: ...
    >>> unauth.open('http://localhost/sections/1/mygrades')
    Traceback (most recent call last):
    ...
    Unauthorized: ...

For managers, the default is to allow them to view. but not edit.

    >>> manager.open('http://localhost/sections/1/gradebook')
    >>> print manager.contents
    <BLANKLINE>
    ...Physics I (1)...
    ...View Final Grades...
    >>> manager.getLink('HW 1').click()
    Traceback (most recent call last):
    ...
    Unauthorized: ...

Administration can't grade students by default but can give itself
the permission to do it:

    >>> manager.open('http://localhost')
    >>> manager.getLink('Manage').click()
    >>> manager.getLink('Access Control').click()
    >>> manager.getControl('Administration can grade students').click()
    >>> manager.getControl('Apply').click()

And try again:

    >>> manager.open('http://localhost/sections/1/gradebook')
    >>> manager.getLink('HW 1').click()
    >>> manager.getControl(name='tom').value = '45'
    >>> manager.getControl('Update').click()

Let's set the setting back to cover our tracks:

    >>> manager.getLink('Manage').click()
    >>> manager.getLink('Access Control').click()
    >>> manager.getControl('Administration can grade students').click()
    >>> manager.getControl('Apply').click()

A teacher should be able to view and edit his own gradebook.

    >>> stephan.open('http://localhost/sections/1/gradebook')
    >>> print stephan.contents
    <BLANKLINE>
    ...Physics I (1)...
    ...View Final Grades...
    >>> stephan.getLink('HW 1').click()
    >>> stephan.getControl(name='tom').value = '44'
    >>> stephan.getControl('Update').click()

Students won't be able to see each other's grade's because the mygrades view
uses the request's principal to determine which grades to display.

    >>> claudia.open('http://localhost/sections/1/mygrades')
    >>> print claudia.contents
    <BLANKLINE>
    ... Current Grade: 86%...
    >>> tom = setup.logIn('tom', 'pwd')
    >>> tom.open('http://localhost/sections/1/mygrades')
    >>> print tom.contents
    <BLANKLINE>
    ...Current Grade: 88%...

Students should not be able to view a teacher's gradebook.

    >>> claudia.open('http://localhost/sections/1/gradebook')
    Traceback (most recent call last):
    ...
    Unauthorized: ...

