=============
The Gradebook
=============

There are many tasks that are involved in setting up and using a
gradebook. The first task the administrator has to complete during the
SchoolTool setup is the configuration of the categories. So let's log in as a
manager:

    >>> from schooltool.app.browser.ftests import setup
    >>> manager = setup.logIn('manager', 'schooltool')

Some imports:

    >>> from schooltool.gradebook import sliceString


Activity Categories
-------------------

Administrator defines activity categories available for teachers.

    >>> manager.getLink('Manage').click()
    >>> manager.getLink('Activity Categories').click()
    >>> analyze.printQuery("id('field.categories')/option/@value", manager.contents)
    essay
    exam
    assignment
    journal
    lab
    project
    presentation
    homework

As you can see, there are already several categories pre-defined. Often,
those categories do not work for a school. Either you do not need some and/or
others are missing. So let's start by deleting a couple of categories:

    >>> manager.getControl(name='field.categories:list').value = [
    ...     'essay', 'journal', 'homework', 'presentation']
    >>> manager.getControl('Remove').click()

    >>> 'Categories successfully deleted.' in manager.contents
    True
    >>> analyze.printQuery("id('field.categories')/option/@value", manager.contents)
    exam
    assignment
    lab
    project

Next, we add a new category:

    >>> manager.getControl('New Category').value = 'Lab Report'
    >>> manager.getControl('Add').click()

    >>> 'Category successfully added.' in manager.contents
    True
    >>> analyze.printQuery("id('field.categories')/option/@value", manager.contents)
    exam
    assignment
    lab
    project
    labreport-

We can also add categories with non ASCII characters:

    >>> manager.getControl('New Category').value = 'Calificación'
    >>> manager.getControl('Add').click()

    >>> analyze.printQuery("id('field.categories')/option/@value", manager.contents)
    exam
    assignment
    calificacin-1ra1s
    lab
    project
    labreport-

If we click on Add without entering a new category, nothing happens:

    >>> analyze.printQuery("id('field.newCategory')/@value", manager.contents)

    >>> manager.getControl('Add').click()
    >>> 'Category successfully added.' in manager.contents
    False

Also click Remove without nothing selected:

    >>> manager.getControl('Remove').click()
    >>> 'Categories successfully deleted.' in manager.contents
    False

We can also change the default category:

    >>> manager.getControl('Default Category').value
    ['assignment']

    >>> manager.getControl('Default Category').value = ['exam']
    >>> manager.getControl('Change').click()

    >>> manager.getControl('Default Category').value
    ['exam']


Initial School Setup
--------------------

Set up the school year and a couple of terms:

   >>> setup.addSchoolYear('2007', '2007-01-01', '2007-12-31')
   >>> setup.addTerm('Winter', '2007-01-01', '2007-06-01', schoolyear='2007')
   >>> setup.addTerm('Fall', '2007-07-01', '2007-12-31', schoolyear='2007')

Next the administrator defines the courses that are available in the school.

    >>> manager.reload()
    >>> manager.getLink('2007').click()
    >>> manager.getLink('Courses').click()
    >>> manager.getLink('New Course').click()
    >>> manager.getControl('Title').value = 'Physics I'
    >>> manager.getControl('Add').click()
    >>> manager.getLink('Physics I').click()

    >>> manager.getLink('2007').click()
    >>> manager.getLink('Courses').click()
    >>> manager.getLink('New Course').click()
    >>> manager.getControl('Title').value = 'English I'
    >>> manager.getControl('Add').click()
    >>> manager.getLink('English I').click()


Term Setup
----------

Every term, the administrators of a school are going to setup sections. So
let's add some sections:

    >>> from schooltool.app.browser.ftests import setup
    >>> setup.addSection('Physics I', '2007', 'Winter')
    >>> setup.addSection('English I', '2007', 'Fall')

But what would a section be without some students and a teacher?

    >>> from schooltool.basicperson.browser.ftests.setup import addPerson
    >>> addPerson('Paul', 'Cardune', 'paul', 'pwd', browser=manager)
    >>> addPerson('Tom', 'Hoffman', 'tom', 'pwd', browser=manager)
    >>> addPerson('Claudia', 'Richter', 'claudia', 'pwd', browser=manager)
    >>> addPerson('Stephan', 'Richter', 'stephan', 'pwd', browser=manager)

Now we can add those people to our sections:

    >>> manager.getLink('2007').click()
    >>> manager.getLink('Courses').click()
    >>> manager.getLink('Physics I').click()
    >>> manager.getLink('(1)').click()

    >>> manager.getLink('edit individuals').click()
    >>> manager.getControl(name='add_item.paul').value = 'checked'
    >>> manager.getControl(name='add_item.tom').value = 'checked'
    >>> manager.getControl(name='add_item.claudia').value = 'checked'
    >>> manager.getControl('Add').click()
    >>> manager.getControl('OK').click()

    >>> manager.getLink('edit instructors').click()
    >>> manager.getControl(name='add_item.stephan').value = 'checked'
    >>> manager.getControl('Add').click()
    >>> manager.getControl('OK').click()

    >>> manager.getLink('2007').click()
    >>> manager.getLink('Courses').click()
    >>> manager.getLink('English I').click()
    >>> manager.getLink('(1)').click()

    >>> manager.getLink('edit individuals').click()
    >>> manager.getControl(name='add_item.paul').value = 'checked'
    >>> manager.getControl(name='add_item.tom').value = 'checked'
    >>> manager.getControl(name='add_item.claudia').value = 'checked'
    >>> manager.getControl('Add').click()
    >>> manager.getControl('OK').click()

    >>> manager.getLink('edit instructors').click()
    >>> manager.getControl(name='add_item.stephan').value = 'checked'
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

Since his section has not yet been set up to have any worksheets, a default
worksheet called, 'Sheet1', will automatically be created.

    >>> stephan = setup.logIn('stephan', 'pwd')
    >>> stephan.getLink('Gradebook').click()
    >>> stephan.getLink('Worksheets').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...Worksheets...
    ...Sheet1...

First, we will change the title of our default worksheet to 'Week 1'.

    >>> stephan.getLink('Sheet1').click()
    >>> stephan.getLink('Edit').click()
    >>> stephan.getControl('Title').value = 'Week 1'
    >>> stephan.getControl('Apply').click()
    >>> 'Week 1' in stephan.contents
    True

We'll note the message that appears for empty worksheets.  Also, the fact that
there's no delete button.

    >>> stephan.getLink('Week 1').click()
    >>> analyze.printQuery("id('content-body')/form/div[1]", stephan.contents)
    <div>This worksheet has no activities.</div>
    >>> analyze.printQuery("id('content-body')/form/div[3]", stephan.contents)
    >>> stephan.getLink('Worksheets').click()

Then, we can use the 'New Worksheet' action link to create our second worksheet.

    >>> stephan.getLink('New Worksheet').click()
    >>> stephan.getControl('Title').value = 'Week 2'
    >>> stephan.getControl('Add').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...Worksheets...
    ...Week 1...
    ...Week 2...

To return to the gradebook for this section, we will click on the
'Return to Gradebook' link.  Since this is the first time Stephan has
entered the gradebook for this section, the current worksheet will default
to the first one.

    >>> stephan.getLink('Return to Gradebook').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...Worksheet...
    ...New Activity...
    ...Manage Activities...
    ...Physics I (1)...
    ...Cardune, Paul...
    ...Hoffman, Tom...
    ...Richter, Claudia...
    >>> '<span style="font-weight: bold;">Week 1</span>' in stephan.contents
    True

Now, let's add some activities to it.  After adding the first activity we'll
note that the new activity appears in the gradebook.

    >>> stephan.getLink('New Activity').click()
    >>> stephan.getControl('Title').value = 'HW 1'
    >>> stephan.getControl('Description').value = 'Homework 1'
    >>> stephan.getControl('Category').value = ['assignment']
    >>> stephan.getControl('Maximum').value = '50'
    >>> stephan.getControl('Add').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...Worksheet...
    ...New Activity...
    ...Manage Activities...
    ...HW 1...

We'll add a second activity.

    >>> stephan.getLink('New Activity').click()
    >>> stephan.getControl('Title').value = 'Quiz'
    >>> stephan.getControl('Description').value = 'Week 1 Pop Quiz'
    >>> stephan.getControl('Category').value = ['exam']
    >>> stephan.getControl('Add').click()
    >>> 'Quiz' in stephan.contents
    True

We'll test editing an activity's description.  To do this, we need to go to use
the 'Manage Activities' link.  This presents us with a view of the current
worksheet's activities with links to edit them.

    >>> stephan.getLink('Manage Activities').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...Edit...
    ...New Activity...
    ...Return to Gradebook...
    ...HW 1...
    ...Quiz...
    ...Delete...

Now let's click on 'HW 1' to change its description.

    >>> stephan.getLink('HW 1').click()
    >>> stephan.getControl('Description').value = 'Homework One'
    >>> stephan.getControl('Apply').click()

Now let's change the current worksheet to 'Week 2'.

    >>> stephan.getLink('Return to Gradebook').click()
    >>> stephan.getLink('Week 2').click()
    >>> '<span style="font-weight: bold;">Week 2</span>' in stephan.contents
    True

Now we'll add some activities to it.

    >>> stephan.getLink('New Activity').click()
    >>> stephan.getControl('Title').value = 'HW 2'
    >>> stephan.getControl('Description').value = 'Homework 2'
    >>> stephan.getControl('Category').value = ['assignment']
    >>> stephan.getControl('Add').click()
    >>> 'HW 2' in stephan.contents
    True
    >>> stephan.getLink('New Activity').click()
    >>> stephan.getControl('Title').value = 'Final'
    >>> stephan.getControl('Description').value = 'Final Exam'
    >>> stephan.getControl('Category').value = ['exam']
    >>> stephan.getControl('Add').click()
    >>> 'Final' in stephan.contents
    True

The 'Manage Activities' view allows for reordering the columns of the gradebook.
We'll switch the order or our two activities.  Since Javascript is not working
in the tests, we submit the form manually:

    >>> stephan.getLink('Manage Activities').click()
    >>> url = stephan.url
    >>> stephan.open(url+'?form-submitted=&pos.Activity=2')
    >>> analyze.printQuery("id('content-body')//a", stephan.contents)
    <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-2/Activity-2">Final</a>
    <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-2/Activity">HW 2</a>

We'll switch them back.

    >>> stephan.open(url+'?form-submitted=&pos.Activity=1')
    >>> analyze.printQuery("id('content-body')//a", stephan.contents)
    <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-2/Activity">HW 2</a>
    <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-2/Activity-2">Final</a>

We'll switch to the Fall term and add some activities to the English I section:

    >>> stephan.open('http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-2/gradebook?currentTerm=2007-.fall-')
    >>> stephan.getLink('New Activity').click()
    >>> stephan.getControl('Title').value = 'Lab 1'
    >>> stephan.getControl('Description').value = 'Laboratory 1'
    >>> stephan.getControl('Category').value = ['assignment']
    >>> stephan.getControl('Add').click()
    >>> 'Lab 1' in stephan.contents
    True
    >>> stephan.getLink('New Activity').click()
    >>> stephan.getControl('Title').value = 'Final'
    >>> stephan.getControl('Description').value = 'Final Exam'
    >>> stephan.getControl('Category').value = ['exam']
    >>> stephan.getControl('Add').click()
    >>> 'Final' in stephan.contents
    True

Finally, we'll change the section back to the Winter Physics section and the
current workskeet back to 'Week 1'.

    >>> stephan.open('http://localhost/schoolyears/2007/winter/sections/1/gradebook/')
    >>> stephan.getLink('Week 1').click()
    >>> '<span style="font-weight: bold;">Week 1</span>' in stephan.contents
    True


Grading
-------

The initial gradebook screen is a simple spreadsheet.  Since we just loaded up
the gradebook for the first time, the current worksheet will be the first one,
Week 1.  Only the activities for that worksheet should appear.

    >>> 'HW 1' in stephan.contents and 'Quiz' in stephan.contents
    True
    >>> 'HW 2' in stephan.contents or 'Final</a>' in stephan.contents
    False

We can enter a score into any cell.  Let's enter one for Claudia's HW 1
activity.  We'll do some trickery to calculate the cell name, taking advantage
of the fact that it's the first cell.

    >>> index = stephan.contents.find('claudia')
    >>> contents = stephan.contents[index:]
    >>> search_text = 'name="'
    >>> index = contents.find(search_text) + len(search_text)
    >>> txt = contents[index:]
    >>> cell_name = txt[:txt.find('"')]
    >>> stephan.getControl(name=cell_name).value = '56'
    >>> stephan.getControl('Save').click()

We should see the score reflected in the spreadsheet.

    >>> stephan.getControl(name=cell_name).value
    '56'

If we enter an invalid score, we will get an error message.

    >>> stephan.getControl(name=cell_name).value = 'Bad'
    >>> stephan.getControl('Save').click()
    >>> 'Invalid scores (highlighted in red) were not saved.' in stephan.contents
    True

We can change the score and see the change reflected in the spreadsheet.

    >>> stephan.getControl(name=cell_name).value = '88'
    >>> stephan.getControl('Save').click()
    >>> stephan.getControl(name=cell_name).value
    '88'

Finally, we can remove the score by clearing out the cell.

    >>> stephan.getControl(name=cell_name).value = ''
    >>> stephan.getControl('Save').click()
    >>> stephan.getControl(name=cell_name).value
    ''

We need to put the score back for future tests to pass.

    >>> stephan.getControl(name=cell_name).value = '36'
    >>> stephan.getControl('Save').click()


Entering Scores for a Column (Activity)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's say we want to enter the grades for Homework 1. All we do is to simply
click on the activity's name:

    >>> stephan.getLink('HW1').click()

Now we just enter the grades. Since Claudia has already a grade, we only need
to grade Paul and Tom:

    >>> stephan.getControl('Cardune, Paul').value = u'-1'
    >>> stephan.getControl('Hoffman, Tom').value = u'42'
    >>> stephan.getControl('Save').click()

Again, we entered an invalid value, this time for Paul:

    >>> 'The grade -1 for Cardune, Paul is not valid.' in stephan.contents
    True

Also note that all the other entered values should be retained:

    >>> 'value="-1"' in stephan.contents
    True
    >>> 'value="42"' in stephan.contents
    True
    >>> 'value="36"' in stephan.contents
    True
    >>> stephan.getControl('Cardune, Paul').value = u'32'
    >>> stephan.getControl('Save').click()

The screen will return to the grade overview, where the grades are now
visible:

    >>> 'value="32"' in stephan.contents
    True
    >>> 'value="42"' in stephan.contents
    True
    >>> 'value="36"' in stephan.contents
    True

Now let's enter again and change a grade:

    >>> stephan.getLink('HW1').click()
    >>> stephan.getControl('Richter, Claudia').value = u'48'
    >>> stephan.getControl('Save').click()
    >>> 'value="48"' in stephan.contents
    True

When you want to delete an evaluation altogether, simply blank the value:

    >>> stephan.getLink('HW1').click()
    >>> stephan.getControl('Richter, Claudia').value = u''
    >>> stephan.getControl('Save').click()
    >>> 'value="98"' in stephan.contents
    False

Of course, you can also abort the grading.

    >>> stephan.getLink('HW1').click()
    >>> stephan.getControl('Cancel').click()
    >>> stephan.url
    'http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet/gradebook/index.html'

Let's enter some grades for the second worksheet, 'Week 2', so that we have
some interesting numbers for the summary view.

    >>> stephan.getLink('Week 2').click()
    >>> stephan.getLink('HW2').click()
    >>> stephan.getControl('Cardune, Paul').value = u'90'
    >>> stephan.getControl('Hoffman, Tom').value = u'72'
    >>> stephan.getControl('Richter, Claudia').value = u'42'
    >>> stephan.getControl('Save').click()

We'll set the current worksheet back to week 1 for the rest of the tests.

    >>> stephan.getLink('Week 1').click()

We need to set Claudia's Quiz score to 86 to replace tests that we deleted.

    >>> stephan.getLink('Quiz').click()
    >>> stephan.getControl('Richter, Claudia').value = u'86'
    >>> stephan.getControl('Save').click()
    >>> stephan.url
    'http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet/gradebook/index.html'


Entering Scores for a Row (Student)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With the introduction of the comment score system, we need to provide the user
with a way of entering comments into the gradebook.  Since comments have
arbitrary length, we need a special view for entering them.  We will provide
a row view (by student) for this purpose.  When the user clicks on a student,
they will see a form with one field for each activity, comments having the
fckEditor widget, the rest of the score system types just having a TextLine
widget.

Additionally, the user will have two special buttons, 'Previous' and 'Next',
which allows them to go from student to student without having to return to
the gradebook spreadsheet each time.  'Apply' and 'Cancel' return to the
spreadsheet as one would expect.

We'll start by clicking on Paul and testing the contents of the form.
Since Paul is the first student in the list of students, there will be
no 'Previous' button.

    >>> stephan.getLink('>', index=0).click()
    >>> analyze.printQuery("id('form')/div[1]/h3", stephan.contents)
    <h3>Enter grades for Cardune, Paul</h3>
    >>> analyze.printQuery("id('form')/div[2]//input", stephan.contents)
    <input id="form-buttons-apply" name="form.buttons.apply" class="submit-widget button-field button-ok" value="Apply" type="submit" />
    <input id="form-buttons-next" name="form.buttons.next" class="submit-widget button-field button-ok" value="Next" type="submit" />
    <input id="form-buttons-cancel" name="form.buttons.cancel" class="submit-widget button-field button-cancel" value="Cancel" type="submit" />

When we click on the 'Next' button it takes us to the middle student, Tom.
Here we will see both a 'Previous' and a 'Next' button.

    >>> stephan.getControl('Next').click()
    >>> analyze.printQuery("id('form')/div[1]/h3", stephan.contents)
    <h3>Enter grades for Hoffman, Tom</h3>
    >>> analyze.printQuery("id('form')/div[2]//input", stephan.contents)
    <input id="form-buttons-apply" name="form.buttons.apply" class="submit-widget button-field button-ok" value="Apply" type="submit" />
    <input id="form-buttons-previous" name="form.buttons.previous" class="submit-widget button-field button-ok" value="Previous" type="submit" />
    <input id="form-buttons-next" name="form.buttons.next" class="submit-widget button-field button-ok" value="Next" type="submit" />
    <input id="form-buttons-cancel" name="form.buttons.cancel" class="submit-widget button-field button-cancel" value="Cancel" type="submit" />

When we click on the 'Next' button it takes us to the last student, Claudia.
Here we will see no 'Next' button.

    >>> stephan.getControl('Next').click()
    >>> analyze.printQuery("id('form')/div[1]/h3", stephan.contents)
    <h3>Enter grades for Richter, Claudia</h3>
    >>> analyze.printQuery("id('form')/div[2]//input", stephan.contents)
    <input id="form-buttons-apply" name="form.buttons.apply" class="submit-widget button-field button-ok" value="Apply" type="submit" />
    <input id="form-buttons-previous" name="form.buttons.previous" class="submit-widget button-field button-ok" value="Previous" type="submit" />
    <input id="form-buttons-cancel" name="form.buttons.cancel" class="submit-widget button-field button-cancel" value="Cancel" type="submit" />

Hitting the 'Cancel' button takes the user back to the gradebook.  We'll
verify this by testing the data cells.

    >>> stephan.getControl('Cancel').click()
    >>> analyze.queryHTML("//input[@class='data']/@value", stephan.contents)
    ['32', '', '42', '', '', '86']

Now we'll go change a cell and come back.

    >>> stephan.getLink('>', index=0).click()
    >>> stephan.getControl(name='form.widgets.Activity-2').value = '85'
    >>> stephan.getControl('Apply').click()

We see the new value where it wasn't before.

    >>> analyze.queryHTML("//input[@class='data']/@value", stephan.contents)
    ['32', '85', '42', '', '', '86']

Let's change that new value to something else.

    >>> stephan.getLink('>', index=0).click()
    >>> stephan.getControl(name='form.widgets.Activity-2').value = '35'
    >>> stephan.getControl('Apply').click()
    >>> analyze.queryHTML("//input[@class='data']/@value", stephan.contents)
    ['32', '35', '42', '', '', '86']

Finally, we'll change it back to the way it was, demonstrating that we can
remove scores in the student gradebook.

    >>> stephan.getLink('>', index=0).click()
    >>> stephan.getControl(name='form.widgets.Activity-2').value = ''
    >>> stephan.getControl('Apply').click()

The data cells are set as before.

    >>> analyze.queryHTML("//input[@class='data']/@value", stephan.contents)
    ['32', '', '42', '', '', '86']


Sorting
~~~~~~~

Another feature of the gradebook is the ability to sort each column in a
descending and ascending fashion. By default the student's name is sorted
alphabetically:

    >>> stephan.contents.find('Carduner, Paul') \
    ...     < stephan.contents.find('Hoffman, Tom') \
    ...     < stephan.contents.find('Richter, Claudia')
    True

Then we want to sort by grade in Homework 1, so we should have:

    >>> url = stephan.url
    >>> stephan.open(url + '?sort_by=Activity')
    >>> stephan.contents.find('Paul') \
    ...     < stephan.contents.find('Tom') \
    ...     < stephan.contents.find('Claudia')
    True

Clicking it again, reverses the order:

    >>> stephan.open(url + '?sort_by=Activity')
    >>> stephan.contents.find('Claudia') \
    ...     < stephan.contents.find('Tom') \
    ...     < stephan.contents.find('Paul')
    True


Category Weighting
------------------

Let's create some category weights for the current worksheet.

    >>> stephan.getLink('Weight Categories').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...Category weights for worksheet Week 1...
    ...Assignment...
    ...Exam...
    ...Lab...
    ...Lab Report...
    ...Project...

First we'll show what happens when a value is invalid.  The only valid weights
will be numbers between 0 and 100.

    >>> stephan.getControl('Assignment').value = u'bad value'
    >>> stephan.getControl('Update').click()
    >>> 'bad value is not a valid weight.' in stephan.contents
    True
    >>> stephan.getControl('Assignment').value = u'-1'
    >>> stephan.getControl('Update').click()
    >>> '-1 is not a valid weight.' in stephan.contents
    True
    >>> stephan.getControl('Assignment').value = u'101'
    >>> stephan.getControl('Update').click()
    >>> '101 is not a valid weight.' in stephan.contents
    True

We'll fill in valid values for Assignment and Exam, but they will not add up
to 100.  We should get an error message to that effect.

    >>> stephan.getControl('Assignment').value = u'35'
    >>> stephan.getControl('Exam').value = u'64'
    >>> stephan.getControl('Update').click()
    >>> 'Category weights must add up to 100.' in stephan.contents
    True

If we get the weights to add up to 100, hitting 'Update' will succeed and return
us to the gradebook.  There we will note the effect of the weighting.

    >>> stephan.getControl('Assignment').value = u'38'
    >>> stephan.getControl('Exam').value = u'62'
    >>> stephan.getControl('Update').click()
    >>> print stephan.contents
    <BLANKLINE>
    ...Claudia...
    ...86.0%</b>...
    ...Tom...
    ...84.0%</b>...
    ...Paul...
    ...64.0%</b>...

Finally, we'll test hitting the 'Cancel' button.  It should return to the
gradebook without changing the weights.

    >>> stephan.getLink('Weight Categories').click()
    >>> stephan.getControl('Exam').value
    '62'
    >>> stephan.getControl('Exam').value = u'85'
    >>> stephan.getControl('Cancel').click()
    >>> stephan.getLink('Weight Categories').click()
    >>> stephan.getControl('Exam').value
    '62'


Column Preferences
------------------

Teachers may want to hide or change the label of the summary columns or, in
the case of the average column, they may want to choose a score system to
be used in converting the average to a discrete value.  To support this, we
provide the column preferences view.

First we will add a custom score system which we will use as a column
preference.

    >>> manager.getLink('Manage').click()
    >>> manager.getLink('Score Systems').click()
    >>> manager.getLink('Add Score System').click()
    >>> url = manager.url + '?form-submitted&UPDATE_SUBMIT&title=Good/Bad'
    >>> url = url + '&displayed1=Good&abbr1=G&value1=1&percent1=70'
    >>> url = url + '&displayed2=Bad&abbr2=B&value2=0&percent2=0'
    >>> manager.open(url)

We'll start by calling up the current column preferences and note that there
are none set yet.

    >>> stephan.getLink('Return to Gradebook').click()
    >>> stephan.getLink('Preferences').click()
    >>> analyze.printQuery("id('content-body')/form//table//input", stephan.contents)
    <input type="checkbox" name="hide_total" />
    <input type="text" name="label_total" value="" />
    <input type="checkbox" name="hide_average" />
    <input type="text" name="label_average" value="" />

    >>> analyze.printQuery("id('content-body')/form//table//option", stephan.contents)
    <option selected="selected" value="">-- No score system --</option>
    <option value="extended-letter-grade">Extended Letter Grade</option>
    <option value="goodbad">Good/Bad</option>
    <option value="letter-grade">Letter Grade</option>
    <option value="passfail">Pass/Fail</option>

    >>> analyze.printQuery("id('content-body')/form//input[@name='hide_due_date']", stephan.contents)
    <input type="checkbox" name="hide_due_date" />

Let's change all preferences

    >>> stephan.getControl(name='hide_total').value = ['on']
    >>> stephan.getControl(name='label_total').value = 'Summe'
    >>> stephan.getControl(name='hide_average').value = ['on']
    >>> stephan.getControl(name='label_average').value = 'Durchschnitt'
    >>> stephan.getControl(name='scoresystem_average').value = ['goodbad']
    >>> stephan.getControl(name='hide_due_date').value = ['on']
    >>> stephan.getControl('Update').click()

Total and average columns were hidden

    >>> results = analyze.queryHTML("//table[@class='schooltool_gradebook'][2]//th/div//text()", stephan.contents)
    >>> results = [result.strip() for result in results]
    >>> for result in results: print result
    Name
    <BLANKLINE>
    HW1
    <BLANKLINE>
    50
    <BLANKLINE>
    Quiz
    <BLANKLINE>
    100

Due date filter was also hidden

    >>> 'show only activities due in past' in stephan.contents
    False

    >>> analyze.printQuery("//select[@name='num_weeks']", stephan.contents)

Look that all the preferences were saved

    >>> stephan.getLink('Preferences').click()
    >>> analyze.printQuery("id('content-body')/form//table//input", stephan.contents)
    <input type="checkbox" checked="checked" name="hide_total" />
    <input type="text" name="label_total" value="Summe" />
    <input type="checkbox" checked="checked" name="hide_average" />
    <input type="text" name="label_average" value="Durchschnitt" />

    >>> analyze.printQuery("id('content-body')/form//table//option", stephan.contents)
    <option value="">-- No score system --</option>
    <option value="extended-letter-grade">Extended Letter Grade</option>
    <option selected="selected" value="goodbad">Good/Bad</option>
    <option value="letter-grade">Letter Grade</option>
    <option value="passfail">Pass/Fail</option>

    >>> analyze.printQuery("id('content-body')/form//input[@name='hide_due_date']", stephan.contents)
    <input type="checkbox" name="hide_due_date" checked="checked" />

Show the total and average columns, and test that Average is converted to Good/Bad:

    >>> stephan.getControl(name='hide_total').value = False
    >>> stephan.getControl(name='hide_average').value = False
    >>> stephan.getControl('Update').click()

    >>> results = analyze.queryHTML("//table[@class='schooltool_gradebook'][2]//th/div//text()", stephan.contents)
    >>> results = [result.strip() for result in results if result]
    >>> for result in results: print result
    Name
    Summe
    Durchschnitt
    <BLANKLINE>
    HW1
    <BLANKLINE>
    50
    <BLANKLINE>
    Quiz
    <BLANKLINE>
    100

    >>> results = analyze.queryHTML("id('content-body')//table//b", stephan.contents)
    >>> results = [result.strip() for result in results]
    >>> for result in results: print result
    <b>86</b>
    <b>Good</b>
    <b>42</b>
    <b>Good</b>
    <b>32</b>
    <b>Bad</b>

Check with extended letter grade scoresystem

    >>> stephan.getLink('Preferences').click()
    >>> stephan.getControl(name='scoresystem_average').value = ['extended-letter-grade']
    >>> stephan.getControl('Update').click()

    >>> results = analyze.queryHTML("id('content-body')//table//b", stephan.contents)
    >>> results = [result.strip() for result in results]
    >>> for result in results: print result
    <b>86</b>
    <b>B</b>
    <b>42</b>
    <b>B</b>
    <b>32</b>
    <b>D</b>

Finally, we will reset the preferences to none so that the rest of the tests
pass.

    >>> stephan.getLink('Preferences').click()
    >>> url = stephan.url + '?form-submitted&UPDATE_SUBMIT'
    >>> url += '&scoresystem_average='
    >>> stephan.open(url)


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
    'http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet/mygrades'
    >>> 'HW 1' in claudia.contents and 'Quiz' in claudia.contents
    True
    >>> 'HW 2' in claudia.contents or 'Final' in claudia.contents
    False
    >>> claudia.contents.find('Ave.: 86%') \
    ...     < claudia.contents.find('HW 1') \
    ...     < claudia.contents.find('Quiz') \
    ...     < claudia.contents.find('86 / 100')
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

    >>> setup.addSection('Physics I', '2007', 'Winter')
    >>> manager.getLink('2007').click()
    >>> manager.getLink('Courses').click()
    >>> manager.getLink('Physics I').click()
    >>> manager.getLink('(2)').click()

    >>> manager.getLink('edit individuals').click()
    >>> manager.getControl(name='add_item.stephan').value = 'checked'
    >>> manager.getControl('Add').click()
    >>> manager.getControl('OK').click()

    >>> manager.getLink('edit instructors').click()
    >>> manager.getControl(name='add_item.tom').value = 'checked'
    >>> manager.getControl('Add').click()
    >>> manager.getControl('OK').click()

We'll have Tom set up a worksheet.

    >>> tom = setup.logIn('tom', 'pwd')
    >>> tom.getLink('Gradebook').click()
    >>> tom.getLink('Classes you teach').click()
    >>> tom.getLink('Worksheets').click()
    >>> tom.getLink('Sheet1').click()
    >>> tom.getLink('Edit').click()
    >>> tom.getControl('Title').value = 'Week 1'
    >>> tom.getControl('Apply').click()

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

The first test will be for the unauthenticated user.  If they hit the
'Gradebook' link at the top, they should be redirected to the login view.

    >>> from zope.testbrowser.testing import Browser
    >>> unauth = Browser()
    >>> unauth.handleErrors = False
    >>> unauth.open('http://localhost/gradebook.html')
    >>> unauth.url
    'http://localhost/auth/@@login.html?nexturl=http://localhost/gradebook.html'

They should not be able to see a gradebook and certainly don't have a mygrades
view.

    >>> unauth.open('http://localhost/schoolyears/2007/winter/sections/1/gradebook')
    Traceback (most recent call last):
    ...
    Unauthorized: ...

    >>> unauth.open('http://localhost/schoolyears/2007/winter/sections/1/mygrades')
    Traceback (most recent call last):
    ...
    Unauthorized: ...

For managers, the default is to allow them to view. but not edit.

    >>> manager.open('http://localhost/schoolyears/2007/winter/sections/1/gradebook')
    >>> print manager.contents
    <BLANKLINE>
    ...Physics I (1)...
    >>> manager.getLink('HW1').click()
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

    >>> manager.open('http://localhost/schoolyears/2007/winter/sections/1/gradebook')
    >>> manager.getLink('HW1').click()
    >>> manager.getControl(name='tom').value = '45'
    >>> manager.getControl('Save').click()

Let's set the setting back to cover our tracks:

    >>> manager.getLink('Manage').click()
    >>> manager.getLink('Access Control').click()
    >>> manager.getControl('Administration can grade students').click()
    >>> manager.getControl('Apply').click()

A teacher should be able to view and edit his own gradebook.

    >>> stephan.open('http://localhost/schoolyears/2007/winter/sections/1/gradebook')
    >>> print stephan.contents
    <BLANKLINE>
    ...Physics I (1)...
    >>> stephan.getLink('HW1').click()
    >>> stephan.getControl(name='tom').value = '44'
    >>> stephan.getControl('Save').click()

Students won't be able to see each other's grade's because the mygrades view
uses the request's principal to determine which grades to display.

    >>> claudia.open('http://localhost/schoolyears/2007/winter/sections/1/mygrades')
    >>> print claudia.contents
    <BLANKLINE>
    ... Ave.: 86.0%...
    >>> tom = setup.logIn('tom', 'pwd')
    >>> tom.open('http://localhost/schoolyears/2007/winter/sections/1/mygrades')
    >>> print tom.contents
    <BLANKLINE>
    ...Ave.: 88.0%...

Students should not be able to view a teacher's gradebook.

    >>> claudia.open('http://localhost/schoolyears/2007/winter/sections/1/gradebook')
    Traceback (most recent call last):
    ...
    Unauthorized: ...


Export Worksheets as XLS
------------------------

Gradebook's worksheets can be exported to a XLS file:

    >>> stephan.getLink('Export XLS').click()
    >>> stephan.headers.get('Content-Type')
    'application/excel'
    >>> stephan.open('http://localhost/gradebook.html')
    >>> stephan.getLink('Classes you teach').click()
    >>> stephan.getLink('Worksheets').click()
    >>> stephan.getLink('Export XLS').click()
    >>> stephan.headers.get('Content-Type')
    'application/excel'


External Activities
-------------------

External activities allow to get grades for a worksheet activity from
another schooltool module.

Before we test external activities, we are going to record the current
state of the gradebook:

    >>> stephan.open('http://localhost/gradebook.html')
    >>> stephan.getLink('Classes you teach').click()
    >>> '<span style="font-weight: bold;">Week 1</span>' in stephan.contents
    True
    >>> stephan.getLink('Manage Activities').click()

We have two regular activities. One assignment:

    >>> stephan.getLink('HW 1').click()
    >>> stephan.getControl('Category').displayValue
    ['Assignment']
    >>> stephan.getControl('Cancel').click()

# XXX Cancel does not return you back where you came from!

    >>> stephan.getLink('Gradebook').click()
    >>> stephan.getLink('Classes you teach').click()
    >>> stephan.getLink('Manage Activities').click()

And one exam:

    >>> stephan.getLink('Quiz').click()
    >>> stephan.getControl('Category').displayValue
    ['Exam']
    >>> stephan.getControl('Cancel').click()

# XXX Cancel does not return you back where you came from!

    >>> stephan.getLink('Gradebook').click()
    >>> stephan.getLink('Classes you teach').click()
    >>> stephan.getLink('Manage Activities').click()

And our grades are:

    >>> stephan.getLink('Return to Gradebook').click()
    >>> stephan.contents
    <BLANKLINE>
    ...Name...Total...Ave...HW 1...Quiz...
    ...Claudia...<b>86</b>...<b>86.0%</b>...86...
    ...Tom...<b>44</b>...<b>88.0%</b>...44...
    ...Paul...<b>32</b>...<b>64.0%</b>...32...

This state should change after we update the grades from external
activities. Remember that the gradebook has weighting defined?:

    >>> stephan.getLink('Weight Categories').click()
    >>> stephan.contents
    <BLANKLINE>
    ...Category weights for worksheet Week 1...
    ...Assignment...38...
    ...Exam...62...
    ...Lab...

This is important since external activities should be weightable. Now,
let's go back to the 'Activities' view of Stephan's teaching
gradebook:

    >>> stephan.getControl('Cancel').click()
    >>> stephan.getLink('Manage Activities').click()

We should have a 'New External Activity' button to add external
activities:

    >>> stephan.contents
    <BLANKLINE>
    ...Edit...
    ...New Activity...New External Activity...
    ...Return to Gradebook...

Let's add a new external activity as an assignment. For this test we
have registered two external utilities stubs titled "Hardware" and
"HTML":

    >>> stephan.getLink('New External Activity').click()
    >>> hardware_token = "samplesource-hardware"
    >>> stephan.contents
    <BLANKLINE>
    ...Add an External Activity...
    >>> stephan.getControl('External Activity').value = [hardware_token]
    >>> stephan.getControl('Category').value = ['assignment']
    >>> stephan.getControl('Points').value = '15'
    >>> stephan.getControl('Add').click()

Adding an external activity gets us back to the gradebook index view
where we can see the external activity which by default has been
loaded with the latest grades:

    >>> stephan.contents
    <BLANKLINE>
    ...Name...Total...Ave...HW 1...Quiz...Hardware...
    ...Claudia...92.00...68.5%...86...6.00...
    ...Tom...53.00...81.5%...44...9.00...
    ...Paul...32...64.0%...32...

Let's edit the external activity. The form doesn't allow to edit the
score system. The edit view also shows an 'Update Grades' button to
recalculate the activity grades from the external activity:

    >>> stephan.getLink('Manage Activities').click()
    >>> stephan.getLink('Hardware').click()
    >>> 'score system' not in stephan.contents
    True
    >>> 'Maximum' not in stephan.contents
    True
    >>> stephan.contents
    <BLANKLINE>
    ...Update Grades...
    ...<h3>Edit External Activity</h3>...
    ...External Activity...Sample Source - Hardware...
    ...Title...Hardware...
    ...Description...Hardware description...
    ...Category...
    ...<option...selected="selected"...value="assignment"...>Assignment...
    ...Points...15...
    >>> stephan.getControl('Title').value = u"Hardware Assignment"
    >>> stephan.getControl('Description').value = "The Hardware assignment"
    >>> stephan.getControl('Points').value = '25'
    >>> stephan.getControl('Apply').click()

Let's go back to the edit form to update the activity's grades using
the 'Update Grades' button:

    >>> stephan.getLink('Manage Activities').click()
    >>> stephan.getLink('Hardware Assignment').click()
    >>> stephan.contents
    <BLANKLINE>
    ...Update Grades...
    ...<h3>Edit External Activity</h3>...
    ...External Activity...Sample Source - Hardware...
    ...Title...Hardware Assignment...
    ...Description...The Hardware assignment...
    ...Category...
    ...<option...selected="selected"...value="assignment"...>Assignment...
    ...Points...25...
    >>> stephan.getLink('Update Grades').click()

This takes us to the gradebook where the averages should have
changed taking into account the weighting:

    >>> stephan.contents
    <BLANKLINE>
    ...Name...Total...Ave...HW 1...Quiz...Hardware As...
    ...Claudia...96.00...68.5%...86...10.00...
    ...Tom...59.00...78.7%...44...15.00...
    ...Paul...32...64.0%...32...


Column Linking
--------------

To add a spreadsheet feature we created LindedColumnActivity objects to allow
the user to pull in columns from other worksheets.  These columns will not only
display the contents of the source column, but the values will be factored
into the average for the worksheet where the linked column activity lives.

There are two types of linked activities, a link to an other worksheet's
activity, or a link to the average column of the worksheet.  Activity links
will use the score system of the source activity whereas worksheet average
links will use an assumed 100 point system.

We'll switch to the Fall term and enter some scores to the English I section:

    >>> stephan.open('http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-2/gradebook?currentTerm=2007-.fall-')
    >>> stephan.getLink('Lab1').click()
    >>> stephan.getControl('Cardune, Paul').value = u'89'
    >>> stephan.getControl('Hoffman, Tom').value = u'72'
    >>> stephan.getControl('Save').click()

    >>> stephan.getLink('Final').click()
    >>> stephan.getControl('Cardune, Paul').value = u'99'
    >>> stephan.getControl('Hoffman, Tom').value = u'88'
    >>> stephan.getControl('Save').click()

We'll test the totals and averages so that we can check the linked values below:

    >>> results = analyze.queryHTML("id('content-body')//table//b", stephan.contents)
    >>> results = [result.strip() for result in results]
    >>> for result in results: print result
    <b>188</b>
    <b>94.0%</b>
    <b>160</b>
    <b>80.0%</b>
    <b>0</b>
    <b>N/A</b>

Now we'll return to the Winter Physics section and add our first linked column
to the Week 1 worksheet:

    >>> stephan.open('http://localhost/schoolyears/2007/winter/sections/1/gradebook/')
    >>> stephan.getLink('Week 1').click()
    >>> stephan.getLink('New Linked Column').click()

First we'll test the contents of the table of available activities and worksheet
averages that can be chosen as the link.  We have to slice and dice the query
results becuase the ... feature is erratic:

    >>> results = analyze.queryHTML("id('content-body')/form/table//td", stephan.contents)
    >>> slice_results = []
    >>> for low, high in [(0, 3), (4, 7), (8, 11), (12, 15), (16, 19), (20, 23)]:
    ...     slice_results.extend(results[low:high])
    >>> for result in slice_results: print result
    <td class="cell padded odd">Winter</td>
    <td class="cell padded odd">Physics I</td>
    <td class="cell padded odd">Week 2</td>
    <td class="cell padded even"></td>
    <td class="cell padded even"></td>
    <td class="cell padded even"></td>
    <td class="cell padded odd"></td>
    <td class="cell padded odd"></td>
    <td class="cell padded odd"></td>
    <td class="cell padded even">Fall</td>
    <td class="cell padded even">English I</td>
    <td class="cell padded even">Sheet1</td>
    <td class="cell padded odd"></td>
    <td class="cell padded odd"></td>
    <td class="cell padded odd"></td>
    <td class="cell padded even"></td>
    <td class="cell padded even"></td>
    <td class="cell padded even"></td>

    >>> results = analyze.queryHTML("id('content-body')/form/table//input", stephan.contents)
    >>> for result in results: print sliceString(result, 'value', '"', endIndex=1, includeEnd=True)
    value="HW 2"
    value="Final"
    value="Average"
    value="Lab 1"
    value="Final"
    value="Average"

We'll add a link to HW 2 from Week 2, then the average of the worksheet from the
Fall English I section, Sheet1:

    >>> stephan.getControl('HW 2').click()
    >>> stephan.getLink('New Linked Column').click()
    >>> stephan.getControl('Average', index=1).click()

The gradebook now has two new columns whose values are pulled in from the
sources of the links.  First we'll test the editable fields:

    >>> results = analyze.queryHTML("id('content-body')//input", stephan.contents)
    >>> results = [result.strip() for result in results]
    >>> for result in results[7:-1]: print sliceString(result, 'value', '"', endIndex=1, includeEnd=True)
    value=""
    value="86"
    value="10.00"
    value="44"
    value=""
    value="15.00"
    value="32"
    value=""
    value=""

Next we'll test the linked column data:

    >>> results = analyze.queryHTML("id('content-body')//table[@class='schooltool_gradebook'][2]//td/span", stephan.contents)
    >>> results = [result.strip() for result in results]
    >>> for result in results: print result
    <span>42</span>
    <span></span>
    <span>72</span>
    <span>80</span>
    <span>90</span>
    <span>94</span>

Finally we'll test the totals and averages:

    >>> results = analyze.queryHTML("id('content-body')//table//b", stephan.contents)
    >>> results = [result.strip() for result in results]
    >>> for result in results: print result
    <b>138.00</b>
    <b>69.1%</b>
    <b>211.00</b>
    <b>76.7%</b>
    <b>216</b>
    <b>86.4%</b>


Hiding Worksheets
-----------------

We want to allow the user to hide a worksheet so that it no longer figures in
the gradebook.  The worksheet will not be deleted from the database, but it
will be ignored in all areas of gradebook management.

We'll add a new worksheet called 'Week 3' and note its presence in the
list.

    >>> stephan.getLink('Worksheets').click()
    >>> stephan.getLink('New Worksheet').click()
    >>> stephan.getControl('Title').value = 'Week 3'
    >>> stephan.getControl('Add').click()
    >>> analyze.printQuery("id('content-body')//a", stephan.contents)
    <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet/manage.html">Week 1</a>
    <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-2/manage.html">Week 2</a>
    <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-3/manage.html">Week 3</a>

We'll make it the user's current worksheet to make sure we can handle hiding
a worksheet that happens to be the current one for the user.

    >>> stephan.getLink('Week 3').click()
    >>> stephan.getLink('Return to Gradebook').click()

Now we'll hide our newly added worksheet, noting its absense from the list.

    >>> stephan.getLink('Worksheets').click()
    >>> stephan.getControl(name='hide:list').value = ['Worksheet-3']
    >>> stephan.getControl('Hide').click()
    >>> analyze.printQuery("id('content-body')//a", stephan.contents)
    <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet/manage.html">Week 1</a>
    <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-2/manage.html">Week 2</a>

Finally, we'll return to the gradebook, noting that it handles the current
worksheet being hidden, changing the current worksheet to the first one that
is not hidden.

    >>> stephan.getLink('Return to Gradebook').click()
    >>> stephan.url
    'http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet/gradebook'


Unhiding Worksheets
-------------------

Now that we can hide worksheets, we need to allow the user to change their mind
and unhide a worksheet they previously hid.  We need to navigate to the
worksheets from which we can call up the view for unhiding worksheets.

    >>> stephan.getLink('Worksheets').click()
    >>> stephan.getLink('Unhide Worksheets').click()

We'll choose the worksheet we just hid and hit the Unhde button.  The view
automatically returns to the worksheets view.  There we see that the worksheet
has reappeared in the worksheets list.

    >>> stephan.getControl(name='unhide:list').value = ['Worksheet-3']
    >>> stephan.getControl('Unhide').click()
    >>> analyze.printQuery("id('content-body')//a", stephan.contents)
    <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet/manage.html">Week 1</a>
    <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-2/manage.html">Week 2</a>
    <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-3/manage.html">Week 3</a>


Sections without Courses
------------------------

A corner case to handle is the gradebook of sections that for some
reason are not related with a course. This can happen if the course is
created, then the section is created and related to the course and
then the course is deleted. Of course that's not a very smart way to
use SchoolTool, but some users have done it.

Let's delete the English I course, which has one section with three
students:

    >>> manager.getLink('Manage').click()
    >>> manager.getLink('School Years').click()
    >>> manager.getLink('2007').click()
    >>> manager.getLink('Courses').click()
    >>> manager.getControl(name='delete.english-i').value = True
    >>> manager.getControl('Delete').click()
    >>> manager.getControl('Confirm').click()

Now, let's go to our orphan section:

    >>> manager.getLink('Manage').click()
    >>> manager.getLink('School Years').click()
    >>> manager.getLink('2007').click()
    >>> manager.getLink('Fall').click()
    >>> manager.getLink('Sections').click()
    >>> manager.getLink('English I (1)').click()

And we can access its gradebook:

    >>> manager.getLink('Gradebook', index=1).click()
    >>> manager.printQuery('//td[@class="active_tab"]')
    <td class="active_tab">
      <span style="font-weight: bold;">Sheet1</span>
    </td>

Now, let's check that the teacher can access the orphan gradebook:

    >>> stephan.getLink('Home').click()
    >>> stephan.getLink('English I').click()
    >>> stephan.getLink('Gradebook', index=1).click()
    >>> stephan.printQuery('//td[@class="active_tab"]')
    <td class="active_tab">
      <span style="font-weight: bold;">Sheet1</span>
    </td>

And the 'view.html' view on the Student gradebook:

    >>> stephan.open('http://localhost/schoolyears/2007/fall/sections/1/activities/Worksheet/gradebook/paul/view.html')
    >>> stephan.printQuery('id("content-header")/h1')
    <h1>Sheet1 for Paul Cardune in - English I (1)</h1>

Now, let's check that a student can access the orphan gradebook:

    >>> claudia.open('http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet/mygrades?currentTerm=2007-.fall-')
    >>> claudia.printQuery('//td[@class="active_tab"]')
    <td class="active_tab">
      <span style="font-weight: bold;">Sheet1</span>
    </td>
    >>> claudia.getControl(name='currentTerm').value = ['2007-.winter-']
    >>> claudia.getForm(index=0).submit()
    >>> claudia.printQuery('//td[@class="active_tab"]')
    <td class="active_tab">
      <span style="font-weight: bold;">Week 1</span>
    </td>
    <td class="active_tab">
      <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-2/mygrades">Week 2</a>
    </td>
    <td class="active_tab">
      <a href="http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet-3/mygrades">Week 3</a>
    </td>


Last visited section tests
--------------------------

The gradebook remembers where a teacher or student was last time they were
in the gradebook, so we will test this.

    >>> stephan.open('http://localhost/schoolyears/2007/winter/sections/1/gradebook')
    >>> claudia.open('http://localhost/schoolyears/2007/winter/sections/1/mygrades')

    >>> stephan.getLink('Gradebook').click()
    >>> stephan.getLink('Classes you teach').click()
    >>> stephan.url
    'http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet/gradebook'

    >>> claudia.getLink('Gradebook').click()
    >>> claudia.url
    'http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet/mygrades'

    >>> stephan.open('http://localhost/schoolyears/2007/fall/sections/1/gradebook')
    >>> claudia.open('http://localhost/schoolyears/2007/fall/sections/1/mygrades')

    >>> stephan.getLink('Gradebook').click()
    >>> stephan.getLink('Classes you teach').click()
    >>> stephan.url
    'http://localhost/schoolyears/2007/fall/sections/1/activities/Worksheet/gradebook'

    >>> claudia.getLink('Gradebook').click()
    >>> claudia.url
    'http://localhost/schoolyears/2007/fall/sections/1/activities/Worksheet/mygrades'

We need to make sure that we can handle the case where the last visited section
was since deleted.  First we'll delete the fall section of Physics.

    >>> manager.getLink('2007').click()
    >>> manager.getLink('Fall').click()
    >>> manager.getLink('Sections').click()
    >>> manager.getControl(name='delete.1').value = True
    >>> manager.getControl('Delete').click()
    >>> manager.getControl('Confirm').click()

Now when Stephan or Claudia hit the Gradebook tab, they get redirected to the
winter term for the Physics section since the fall section is gone.

    >>> stephan.getLink('Gradebook').click()
    >>> stephan.getLink('Classes you teach').click()
    >>> stephan.url
    'http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet/gradebook'

    >>> claudia.getLink('Gradebook').click()
    >>> claudia.url
    'http://localhost/schoolyears/2007/winter/sections/1/activities/Worksheet/mygrades'


Average tests
-------------

When we weren't using the same method to calculate the average in the gradebook
and the mygrades views, that led to the averages sometimes coming out differently.
Here we will test the the average is the same for Claudia in both views.

    >>> stephan.open('http://localhost/schoolyears/2007/winter/sections/1/gradebook')
    >>> stephan.printQuery("id('content-body')//table[2]/tr[4]/td[3]/b")
    <b>69.1%</b>

    >>> claudia.open('http://localhost/schoolyears/2007/winter/sections/1/mygrades')
    >>> claudia.printQuery("id('content-body')//table[2]/tr[1]/td[1]/div")
    <div> Ave.: 69.1%</div>


CSV test
--------

We supply a CSV view for getting all grades out of schooltool in CSV format.

    >>> manager.getLink('Manage').click()
    >>> manager.getLink('Download Gradebook CSV').click()
    >>> print manager.contents
    "year","term","section","worksheet","activity","student","grade"
    "2007","winter","1","Worksheet","Activity-2","claudia","86"
    "2007","winter","1","Worksheet","LinkedActivity","claudia","10.00"
    "2007","winter","1","Worksheet","LinkedColumnActivity","claudia","42"
    "2007","winter","1","Worksheet","Activity","paul","32"
    "2007","winter","1","Worksheet","LinkedColumnActivity","paul","90"
    "2007","winter","1","Worksheet","Activity","tom","44"
    "2007","winter","1","Worksheet","LinkedActivity","tom","15.00"
    "2007","winter","1","Worksheet","LinkedColumnActivity","tom","72"
    "2007","winter","1","Worksheet-2","Activity","claudia","42"
    "2007","winter","1","Worksheet-2","Activity","paul","90"
    "2007","winter","1","Worksheet-2","Activity","tom","72"

