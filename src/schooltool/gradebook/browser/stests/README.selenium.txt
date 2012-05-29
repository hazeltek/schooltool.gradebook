=============================================
SchoolTool Gradebook Selenium Testing Support
=============================================

Browser extensions
==================

Most of the extensions are coded in the stesting.py module of the
schooltool.gradebook package.

We have browser extensions for:

Printing a worksheet
--------------------

* browser.ui.gradebook.worksheet.pprint()

  Optional keyword parameters:
    show_validation: bool

  NOTE: the current url must be the worksheet's url

  NOTE: if show_validation is set, a code will be printed next to the
  input field. The codes meaning are:

    * v: valid score
    * e: extra credit score
    * i: invalid score

Scoring an activity for a student
---------------------------------

* browser.ui.gradebook.worksheet.score()

  Required parameters:
    student: title of the student row
    activity: label of the column
    grade

  NOTE: the current url must be the worksheet's url
