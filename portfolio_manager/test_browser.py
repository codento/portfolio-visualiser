##
#
# Portfolio Visualizer
#
# Copyright (C) 2017 Codento
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##
# coding=utf-8

import time, datetime
from decimal import Decimal
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils.timezone import get_current_timezone
from django.utils.translation import get_language
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.webdriver import WebDriver as Firefox
from selenium.webdriver.firefox.webdriver import FirefoxProfile
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from portfolio_manager.models import Project, Organization, NumberDimension, DateDimension, AssociatedPersonDimension,\
    AssociatedPersonsDimension, Person, TextDimension, AssociatedProjectsDimension
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from django.utils.formats import localize_input, number_format
from pyvirtualdisplay import Display
from pyvirtualdisplay.xvfb import XvfbDisplay
from easyprocess import EasyProcessCheckInstalledError

USE_XVFB = True

try:
    XvfbDisplay.check_installed()
except EasyProcessCheckInstalledError:
    USE_XVFB = False


WAIT = 5

class BrowserTestCase(StaticLiveServerTestCase):
    """ These tests take longer to run than other tests because they pop up a browser window, a headless one in
    linux/x-window supporting system, real firefox in others. Instead of launching a new firefox for each test, I have
    modified this to use only one instance and just reload pages -- browser is set up in *setUpClass*, not in setUp.
    When we have login cookies etc., those tests better run in 'clean' browser, but here reusing the browser
    doesn't seem to cause problems.
    """
    vdisplay = None
    selenium = None
    fixtures = ['organizations', 'persons_browser_testing', 'projects_browser_testing', 'project_templates']

    @classmethod
    def setUpClass(cls):
        StaticLiveServerTestCase.setUpClass()
        if USE_XVFB:
            # Start xvfb for Firefox
            cls.vdisplay = Display(visible=0, size=(1024, 768))
            cls.vdisplay.start()

    def setUp(self):
        StaticLiveServerTestCase.setUp(self)
        profile = FirefoxProfile()
        # Browser itself attempts to validate form fields before they are sent to django.
        # Fields where input type="Number" accept "100.0" when locale is "en" and "100,0" when locale is "fi", and when
        # they reject the value, django sees an empty value instead.
        # To prevent this causing more problems, force browser used by tests to use same locale as django, typically
        # "en".
        # We may want to occassionally test with other locales, so localize_input, number_format etc. when entering
        # and reading decimals/floats.
        profile.set_preference("intl.accept_languages", get_language())
        profile.set_preference("general.useragent.locale", get_language())
        self.selenium = Firefox(firefox_profile=profile, executable_path='node_modules/geckodriver/geckodriver')
        self.selenium.maximize_window()

    @classmethod
    def tearDownClass(cls):
        if USE_XVFB:
            cls.vdisplay.stop()
        StaticLiveServerTestCase.tearDownClass()

    def tearDown(self):
        self.selenium.quit()
        StaticLiveServerTestCase.tearDown(self)

    # Helper methods for this test case:

    def open(self, url):
        self.selenium.get("%s%s" % (self.live_server_url, url))

    def find(self, element_id):
        return self.selenium.find_element_by_id(element_id)

    def find_css(self, css_selector):
        elems = self.selenium.find_elements_by_css_selector(css_selector)
        found = len(elems)
        if found == 1:
            return elems[0]
        elif not elems:
            raise NoSuchElementException(css_selector)
        return elems

    def assert_wait(self, until, timeout_msg):
        good = False
        try:
            WebDriverWait(self.selenium, WAIT).until(until)
            good = True
        except TimeoutException:
            pass
        self.assertTrue(good, timeout_msg)

    def assert_that_css_appears(self, css_selector):
        self.assert_wait(
            lambda _: self.find_css(css_selector),
            "CSS selector '%s' failed to appear." % css_selector)

    def assert_that_element_appears(self, element_id):
        self.assert_wait(
            EC.visibility_of_element_located((By.ID, element_id)),
            "Element with id '%s' failed to appear." % element_id)

    def assert_that_element_disappears(self, element_id):
        self.assert_wait(
            EC.invisibility_of_element_located((By.ID, element_id)),
            "Element with id '%s' is still there." % element_id)

    def assert_that_text_appears(self, css_selector, text):
        self.assert_wait(
            EC.text_to_be_present_in_element(
                (By.CSS_SELECTOR, css_selector), text),
            "Text '%s' failed to appear in '%s'." % (text, css_selector))

    def assert_wait_that_element_clickable(self, element_id):
        self.assert_wait(
            EC.element_to_be_clickable((By.ID, element_id)),
            "{} failed to become clickable".format(element_id)
        )

    # Actual tests

    def test_add_organization_add_project(self):
        """Add new organization and new project under that organization"""
        #   Add person that will act as project manager later
        project_project_manager = Person.objects.get(pk=2)

        self.open(reverse('admin_tools'))

        organization_name = 'Great organization'
        org_input = self.find('orgName')
        org_input.send_keys(organization_name)
        self.find('org-form').submit()

        # Wait for modal to open
        self.assert_that_css_appears('#conf-modal-body')

        # Reload organizations in "Add project" modal
        self.open(reverse('admin_tools'))

        # Fill in "Add project" form on Admin tools page and submit it
        time.sleep(1)
        project_name = "Great project"
        self.find('id_name').send_keys(project_name)
        Select(self.find('id_organization')).select_by_value(organization_name)
        self.find('pre-add-project-form').submit()

        # Wait for add project page to open up
        self.assert_that_element_appears('id_add_project_form-name')
        # Wait for javascript to populate fields
        time.sleep(1)

        organization = Organization.objects.get(pk=organization_name)

        # Fill in the details of new project and hit submit
        budget_field, end_date_field, project_manager_field, *foo = organization.templates.all()[0].dimensions.all()
        project_budget = 135151.0
        project_end_date = datetime.datetime(2015, 8, 1, tzinfo=get_current_timezone())
        date_in = project_end_date.strftime("%d/%m/%Y")

        self.find('id_{}_form-value'.format(budget_field.id)).send_keys(localize_input(project_budget))
        self.find('id_{}_form-value'.format(end_date_field.id)).send_keys(date_in)
        project_manager_input = self.find('id_{}_form-value'.format(project_manager_field.id))
        Select(project_manager_input).select_by_value(str(project_project_manager.id))
        self.find('add-project-form').submit()

        # Wait until user is redirected to "Show project" page and check that page contains
        # correct information
        self.assert_that_element_appears('project-dimension-panels')
        self.assertEquals(project_name, self.find('project-name').text)
        # TODO: Add search for panel with owningorganization
        # self.assertEquals(organization_name, self.find('projectparent').text)
        end_date = project_end_date.strftime("%d/%m/%Y %H:%M")
        self.assertEquals(end_date, self.find('EndDate').text)
        self.assertEquals(str(project_project_manager), self.find('ProjectManager').text)
        budget = number_format(project_budget, decimal_pos=2)
        self.assertEquals(budget, self.find('Budget').text)

    def test_add_project_from_admin_tools(self):
        """Add project from admin tools"""
        self.open(reverse('admin_tools'))
        self._test_add_project()

    def test_add_project_from_homepage(self):
        """Add project from homepage"""
        self.open(reverse('homepage'))
        self.find('add-project-btn').click()

        # Wait until pre add project form is loaded
        self.assert_that_element_appears('id_name')

        self._test_add_project()

    def _test_add_project(self):
        project_name = "FooBar"
        organization = Organization.objects.get(pk=1)

        # Fill in details of new project and click "Continue"
        self.find('id_name').send_keys(project_name)
        Select(self.find('id_organization')).select_by_value(organization.pk)
        self.find('pre-add-project-form').submit()

        # Wait for "Add project" page to load
        self.assert_that_element_appears('id_add_project_form-name')

        # Check that project name and organization are propertly transmitted from pre add project form
        self.assertEquals(project_name, self.find('id_add_project_form-name').get_attribute('value'))
        self.assertEquals(organization.pk, self.find('id_add_project_form-organization').get_attribute('value'))

        # Fill in the detail of new project and submit
        phase_field, budget_field, *foo = organization.templates.all()[0].dimensions.all()
        project_phase = "Adding-Project"
        project_budget = 135151.0

        self.find('id_{}_form-value'.format(phase_field.id)).send_keys(project_phase)
        self.find('id_{}_form-value'.format(budget_field.id)).send_keys(localize_input(project_budget))
        self.find('add-project-form').submit()

        # Wait for "Show project" to load
        self.assert_that_element_appears('project-dimension-panels')

        # Check that "Show project" page contains correct information
        self.assertEquals(project_name, self.find('project-name').text)
        # TODO: Add search for panel with owningorganization
        # self.assertEquals(organization_name, self.find('projectparent').text)
        self.assertEquals(project_phase, self.find('Phase').text)
        budget = number_format(project_budget, decimal_pos=2)
        self.assertEquals(budget, self.find('Budget').text)

        # Check that correct information is loaded to db
        project = Project.objects.get(name=project_name)
        self.assertIsInstance(project, Project)
        self.assertEquals(organization, project.parent)
        phase_dim, budget_dim, *leftovers = project.dimensions.all()
        self.assertFalse(leftovers)
        self.assertIsInstance(phase_dim.dimension_object, TextDimension)
        self.assertIsInstance(budget_dim.dimension_object, NumberDimension)

        self.assertEquals(Decimal(project_budget), budget_dim.dimension_object.value)
        self.assertEquals(project_phase, phase_dim.dimension_object.value)

    def _test_modify_project_dimension(self, dimension_name, field_type, new_value, cmp_value):
        self.open(reverse('show_project', args=(1,)))

        # Click the "Modify" button of the dimension
        self.find('{}-modifybtn'.format(dimension_name)).click()

        # Wait for modal to open up
        self.assert_that_element_appears('{}-value'.format(field_type))
        self.assert_that_element_appears('modify-{}-modal'.format(field_type))

        # Update form value and submit
        elem = self.find('{}-value'.format(field_type))
        time.sleep(1)
        elem.send_keys(new_value)
        elem.send_keys(Keys.RETURN)
        self.find_css('#modify-{}-form button[type="submit"]'.format(field_type)).click()

        # Wait for modal to close
        self.assert_that_element_disappears('{}-value'.format(field_type))
        self.assert_that_element_disappears('modify-{}-modal'.format(field_type))

        # Refresh the page
        self.open(reverse('show_project', args=(1,)))
        # Check that dimension value was updated
        self.assertEquals(cmp_value, self.find(dimension_name).text)

    def test_modify_project_text_dimension(self):
        """Modifying Phase field from show_project"""
        self._test_modify_project_dimension('Phase', 'text', 'Done', 'Done')

    def test_modify_project_number_dimension(self):
        """Modifying Budget field from show_project"""
        result = number_format(38.00, decimal_pos=2)
        self._test_modify_project_dimension('Budget', 'number', localize_input(38.00), result)

    def test_modify_project_date_dimension(self):
        """Modifying End date from show_project"""
        project_end_date = datetime.datetime(2015, 9, 1, tzinfo=get_current_timezone())
        date_in = project_end_date.strftime("%d/%m/%Y")
        result = project_end_date.strftime("%d/%m/%Y %H:%M")
        self._test_modify_project_dimension('EndDate', 'date', date_in, result)

    def test_modify_project_associated_person_dimension(self):
        """Change ProjectManager"""
        self.open(reverse('show_project', args=(1,)))

        # Click "Modify" button of ProjectManager dimension
        self.find('ProjectManager-modifybtn').click()

        # Wait for modal to open up
        self.assert_that_element_appears('associatedperson-value')
        self.assert_that_element_appears('modify-associatedperson-modal')

        # Select another person from dropdown and submit the form
        Select(self.find('associatedperson-value')).select_by_value('2')
        self.find_css('#modify-associatedperson-form button[type="submit"]').click()

        #Wait for modal to close
        self.assert_that_element_disappears('modify-associatedperson-modal')

        # Refresh the page
        self.open(reverse('show_project', args=(1,)))

        # Check that dimension value is updated
        self.assertEquals(str(Person.objects.get(id=2)), self.find('ProjectManager').text)

    def test_modify_project_associated_persons_dimension_remove(self):
        """Remove a Member"""
        self.open(reverse('show_project', args=(1,)))

        # Click "Modify" of Members dimension
        self.find('Members-modifybtn').click()

        # Wait for modal to open up
        self.assert_that_element_appears('modify-associatedpersons-modal')
        self.assert_that_element_appears('associatedpersons-value')

        # Click to remove the only associated person
        self.find_css('#multiple-associatedpersons-1 button[type="submit"]').click()

        # Refresh page
        self.open(reverse('show_project', args=(1,)))

        p = Person.objects.get(pk=1)
        persons = AssociatedPersonsDimension.objects.get(pk=1).value.all()
        self.assertFalse(p in persons)

    def test_modify_project_associated_persons_dimension_add(self):
        """Add a Member"""
        self.open(reverse('show_project', args=(1,)))

        # Click "Modify" of Members dimension
        self.find('Members-modifybtn').click()

        # Wait for modal to open up
        self.assert_that_element_appears('associatedpersons-value')
        self.assert_that_element_appears('modify-associatedpersons-modal')

        # Select person to add and click '+'
        Select(self.find('associatedpersons-value')).select_by_value('2')
        self.find_css('#modify-associatedpersons-form button[type="submit"]').click()

        # Reload page
        self.open(reverse('show_project', args=(1,)))

        # Click "Modify" of Members dimension
        self.find('Members-modifybtn').click()

        # Wait for modal to open up
        self.assert_that_element_appears('associatedpersons-value')
        self.assert_that_element_appears('modify-associatedpersons-modal')

        # Modal should list new member (2 members + addform)
        self.assertEquals(3, len(self.selenium.find_elements_by_css_selector('#associatedpersons-well-ul li')))

    def test_modify_project_associated_projects_dimension_remove(self):
        """Remove a ProjectDependency"""
        self.open(reverse('show_project', args=(1,)))

        # Click "Modify" of Dependencies dimension
        self.find('Dependencies-modifybtn').click()

        # Wait for modal to open up
        self.assert_that_element_appears('modify-associatedprojects-modal')
        self.assert_that_element_appears('associatedprojects-value')

        # Click to remove the only associated project
        self.find_css('#multiple-associatedprojects-1 button[type="submit"]').click()



        # Refresh page
        self.open(reverse('show_project', args=(1,)))

        # Click "Modify" of Dependencies dimension
        self.find('Dependencies-modifybtn').click()

        # Wait for modal to open up
        self.assert_that_element_appears('modify-associatedprojects-modal')
        self.assert_that_element_appears('associatedprojects-value')

        # Check that it was removed in the database
        p = Project.objects.get(pk=1)
        projects = AssociatedProjectsDimension.objects.get(pk=1).value.all()
        self.assertFalse(p in projects)

        # Modal should not list any members only add the addform
        self.assertEquals(1, len(self.selenium.find_elements_by_css_selector('#associatedprojects-well-ul li')))

    def test_modify_project_associated_projects_dimension_add(self):
        """Add ProjectDependency"""
        self.open(reverse('show_project', args=(1,)))

        # Click "Modify" of Dependencies dimension
        self.find('Dependencies-modifybtn').click()

        # Wait for modal to open up
        self.assert_that_element_appears('associatedprojects-value')
        self.assert_that_element_appears('modify-associatedprojects-modal')

        # Select project to add and click '+'
        Select(self.find('associatedprojects-value')).select_by_value('2')
        self.find_css('#modify-associatedprojects-form button[type="submit"]').click()

        self.open(reverse('show_project', args=(1,)))

        # Click "Modify" of Dependencies dimension
        self.find('Dependencies-modifybtn').click()

        # Wait for modal to open up
        self.assert_that_element_appears('associatedprojects-value')
        self.assert_that_element_appears('modify-associatedprojects-modal')

        # Check that it was added to the database
        p = Project.objects.get(pk=2)
        projects = AssociatedProjectsDimension.objects.get(pk=1).value.all()
        self.assertTrue(p in projects)

        # Modal should've added dependency(2 projects + addform)
        self.assertEquals(3, len(self.selenium.find_elements_by_css_selector('#associatedprojects-well-ul li')))


    def test_add_path_snapshot(self):
        self.open(reverse('path'))

        self.assert_wait_that_element_clickable('project-selector')
        Select(self.find('project-selector')).select_by_value("1")

        self.find('save-path-snap-btn').click()

        self.assert_that_element_appears('save-path-snap-modal')
        self.find('path-snap-name').send_keys("PathSnapTest")
        self.find('path-snap-desc').send_keys("PathSnapTestDescription")

        self.find_css('#save-path-snap-form input[type="submit"]').click()

        self.assert_that_element_appears('snap-info-cont')


    def test_add_fourfield_snapshot(self):
        self.open(reverse('fourfield'))

        self.assert_wait_that_element_clickable('x-selector')

        self.find('save-fourfield-snap-btn').click()

        self.assert_that_element_appears('save-fourfield-snap-modal')
        self.find('fourfield-snap-name').send_keys("FourFieldSnapTest")
        self.find('fourfield-snap-desc').send_keys("FourFieldSnapTestDescription")

        self.find_css('#save-fourfield-snap-form input[type="submit"]').click()

        self.assert_that_element_appears('snap-info-cont')
