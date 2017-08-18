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
import logging
import pytz
import time
import json as json_module
from django.core.serializers.json import DjangoJSONEncoder
import datetime as dt
from itertools import groupby
from collections import defaultdict
from dateutil.parser import parse

import django.forms
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.models import User
from django.contrib.auth.views import login,logout
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse

from portfolio_manager.models import *
from portfolio_manager.forms import *
from portfolio_manager.serializers import ProjectSerializer, \
                                          OrganizationSerializer, \
                                          PersonSerializer, \
                                          ProjectNameIdSerializer
from portfolio_manager.importer import from_google_sheet
from portfolio_manager.authhelper import get_signin_url, get_token_from_code, \
                                         get_access_token
from portfolio_manager.outlookservice import get_me, \
                                             get_and_import_my_sheet, \
                                             get_my_drive

from portfolio_manager.exporter import get_data_array

# LOGGING
logger = logging.getLogger('django.request')


def signup(request):
    if request.method == "POST":
        user = User.objects.create_user(
            username=request.POST['username'],
            email=request.POST.get('email'),
            password=request.POST['password'],
            first_name=request.POST.get('first_name'),
            last_name=request.POST.get('last_name')
        )
        user.save()
        return redirect('homepage')
    else:
        return render(request, 'registration/signup.html')


def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


@login_required
def microsoft_signin(request):
    redirect_uri = request.build_absolute_uri(reverse('gettoken'))
    sign_in_url = get_signin_url(redirect_uri)
    return redirect(sign_in_url)


@login_required
def gettoken(request):
    try:    # Check if the user already has connected
        request.user.m365connection
    except:
        auth_code = request.GET['code']
        redirect_uri = request.build_absolute_uri(reverse('gettoken'))
        token = get_token_from_code(auth_code, redirect_uri)
        access_token = token['access_token']
        user = get_me(access_token)
        refresh_token = token['refresh_token']
        expires_in = token['expires_in']

        # expires_in is in seconds
        # Get current timestamp (seconds since Unix Epoch) and
        # add expires_in to get expiration time
        # Subtract 5 minutes to allow for clock differences
        expiration = int(time.time()) + expires_in - 300

        m365 = Office365Connection()
        m365.user = request.user
        m365.access_token = access_token
        m365.refresh_token = refresh_token
        m365.expiration = expiration
        m365.microsoft_email = user['mail']
        m365.save()

    return redirect('excel')


@login_required
def excel(request):
    #   Get access token
    try:
        access_token = get_access_token(request, request.build_absolute_uri(reverse('gettoken')))
        user_email = request.user.m365connection.microsoft_email
    except Exception as e:  # There is no access_token
        return redirect('microsoft_signin')

    excels = get_my_drive(access_token, user_email)
    context = { 'excels': excels }

    return render(request, 'excel.html', context)


@login_required
def import_excel(request):
    #   Get access token
    try:
        access_token = get_access_token(request, request.build_absolute_uri(reverse('gettoken')))
        user_email = request.user.m365connection.microsoft_email
    except KeyError as e:  # There is no access_token
        return redirect('microsoft_signin')

    excel_id = request.GET['item_id']
    sheet = get_and_import_my_sheet(access_token, user_email, excel_id)
    return redirect('projects')


@login_required
def home(request):
    if not request.user.is_authenticated():
        return redirect('login')
    # milestones for project sneak peeks
    # (only future milestones), ordered by date
    now = datetime.now()
    milestones = Milestone.objects.filter(due_date__gte = now)
    ordered_milestones = milestones.order_by('due_date')

    # dictionary for (project -> next milestone)
    mils = {}
    # Loop through the milestones
    for m in ordered_milestones:
        # Checks if m.project is already in the dictionary for next milestone
        if m.project not in mils:
            mils[m.project] = m.due_date

    # dimensions for project manager and end date of project
    # for project sneak peeks
    dims = ProjectDimension.objects.all()
    # ContentType
    assPersonD = ContentType.objects.get_for_model(AssociatedPersonDimension)
    dated = ContentType.objects.get_for_model(DateDimension)
    # Get dimensions of correct content_type for assPersonDs and dateds
    assPersonDs = dims.filter(content_type=assPersonD)
    dateds = dims.filter(content_type=dated)


    context = {}
    context["projects"] = Project.objects.all()
    context["pre_add_project_form"] = AddProjectForm()
    context['assPerson'] = assPersonDs
    context["mils"] = mils
    context['dates'] = dateds
    return render(request, 'homepage.html', context)


@login_required
def admin_tools(request):
    form = AddProjectForm()
    form.fields['name'].widget.attrs['class'] = 'form-control'
    form.fields['organization'].widget.attrs['class'] = 'form-control'
    return render(request, 'manage/admin_tools.html', {'pre_add_project_form': form})


@login_required
def milestones(request):
    context = {
        'milestones': {},
        'fields': {},
        'fieldToId': defaultdict(lambda: {})
    }
    milestones = Milestone.objects.all().order_by('project')

    if request.method == 'POST':
        fields = {}
        for key, value in request.POST.items():
            if key == 'pid':
                pid = value
            elif key == 'due_date':
                due_date = parse(value, yearfirst=True)
            else:
                fields[key] = value

        if pid and due_date:
            project = Project.objects.get(pk=pid)

            mile = Milestone()
            mile.project = project
            if due_date.tzinfo is None or due_date.tzinfo.utcoffset(due_date) is None:
                due_date = due_date.replace(tzinfo=pytz.utc)
            mile.due_date = due_date
            mile.save()

            for proj_dim_id, value in fields.items():
                proj_dim = ProjectDimension.objects.get(pk=proj_dim_id)

                dim_mile_object = NumberMilestone()
                dim_mile_object.from_sheet(value)
                dim_mile_object.save()

                dim_mile = DimensionMilestone()
                dim_mile.milestone = mile
                dim_mile.dimension_milestone_object = dim_mile_object
                dim_mile.project_dimension = proj_dim
                dim_mile.save()

    grouped_miles = groupby(milestones, lambda milestone: milestone.project)
    for project, milestones in grouped_miles:
        context['milestones'][project] = []
        context['fields'][project] = set()
        for milestone in sorted(list(milestones), key=lambda m: m.due_date):
            data = milestone.get_display_data()
            context['fieldToId'][project].update(data['dimensions_ids'])
            context['milestones'][project].append(data)
            for field, field_data in data['dimensions'].items():
                context['fields'][project].add(field)


    return render(request, 'manage/milestones.html', context)


# TODO: Require admin
@login_required
def add_user(request):
    context = {}
    if request.method == 'POST':
        org = request.user.groups.first()
        user = User.objects.create_user(
            username=request.POST['username'],
            email=request.POST.get('email'),
            password=request.POST['password'],
            first_name=request.POST.get('first_name'),
            last_name=request.POST.get('last_name')
        )
        user.save()
        user.groups.add(org)
        context['successmsg'] = '{} created successfully!'.format(str(user))
    return render(request, 'manage/add_user.html', context)


@require_POST
@login_required
def create_org(request):
    data = {'name': request.POST.get('orgName')}
    form = OrganizationForm(data)
    if form.is_valid():
        # Save a new Organization
        organization = Organization(name = form.cleaned_data['name'])
        organization.save()

        ###     RESPONSE    ###
        response_data = {}
        response_data['result'] = 'Created organization successfully!'
        response_data['orgName'] = organization.name
        return HttpResponse(
            json_module.dumps(response_data),
            content_type="application/json"
        )


@require_POST
@login_required
def create_person(request):
    first = request.POST.get('first')
    last = request.POST.get('last')
    data = {'first': first, 'last': last}
    form = PersonForm(data)
    if form.is_valid():
        person_data = {
            'first_name': form.cleaned_data['first'],
            'last_name': form.cleaned_data['last'],
        }
        person = Person(**person_data)
        person.save()

        response_data = {}
        response_data['result'] = 'Created person successfully!'
        response_data['name'] = str(person)
        return HttpResponse(
            json_module.dumps(response_data),
            content_type="application/json"
        )


@require_POST
@login_required
def add_field(request):
    try:
        form = ProjectTemplateForm(request.POST)
        org = Organization.objects.get(pk=request.POST['organization'])
        template = ProjectTemplate.objects.get(organization=org)
        ct = ContentType.objects.get_for_id(request.POST['field_type'])
        template_dim_data = {
            'name': request.POST['name'],
            'template': template,
            'content_type': ct,
        }
        template_dim = ProjectTemplateDimension(**template_dim_data)
        template_dim.save()

        add_field_form = ProjectTemplateForm()
        add_field_form.initial = {'organization': org.name}
        orgform = OrgForm({'orgs': org})
        # (dimension name -> datatype) dictionary
        dims = {}
        templates = org.templates.all()
        if len(templates) > 0:
            template = templates[0]
            for t_dim in template.dimensions.all():
                #TODO: group them by types to make the site easier to view?
                t_dim_name = t_dim.content_type.model_class().__name__
                dims[t_dim.name] = str(t_dim_name).replace("Dimension", "")

        resultmsg = "Successfully added the \"%s\"-field" % request.POST['name']
        render_data = {
            'form': orgform,
            'dims': dims,
            'add_field_form': add_field_form,
            'add_field_success': resultmsg,
        }
        return render(request, 'database.html', render_data)
    except Exception as e:
        orgform = OrgForm()
        add_field_form = ProjectTemplateForm()
        resultmsg = "ERROR: %s" % e
        print(resultmsg)
        render_data = {
            'form': orgform,
            'add_field_form': add_field_form,
            'add_field_fail': resultmsg,
        }
        return render(request, 'database.html', render_data)


@login_required
def show_project(request, project_id):
    all_projects = Project.objects.all()
    project = all_projects.get(pk=project_id)
    project_dims = project.dimensions.all()
    template_dims = ProjectTemplate.objects.get(organization=project.parent).dimensions.all()

    dimensions = {}
    for k, g in groupby(template_dims, lambda x: x.content_type):
        for dim in list(g):
            ct = ContentType.objects.get(id=k.id)
            dimensions.setdefault(ct, {}).update({dim.name: None})

    for key, value in dimensions.items():
        dims_of_key = project_dims.filter(content_type=key)
        for d in dims_of_key:
            if d.dimension_object.name in value:
                dimensions[key][d.dimension_object.name] = d.dimension_object

    context = {}
    context['project'] = project
    context['projects'] = all_projects
    context['dimensions'] = dimensions

    return render(request, 'project.html', context)


# Function that edits a project by either updating, adding or removing values
@login_required
def project_edit(request, project_id, field_type):
    type_to_dimension = {
        'text': TextDimension,
        'number': NumberDimension,
        'date': DateDimension,
        'associatedperson': AssociatedPersonDimension,
        'associatedorganization': AssociatedOrganizationDimension,
        'associatedpersons': AssociatedPersonsDimension,
        'associatedprojects': AssociatedProjectsDimension
    }
    if request.method == "POST":
        data = request.POST
        field = data.get('field')
        value = data.get('value')
        if not is_int(field):
            dimension = type_to_dimension[field_type]()
            dimension.value = value
            dimension.name = field
            dimension.save()

            projdim = ProjectDimension()
            projdim.dimension_object = dimension
            projdim.project = Project.objects.get(pk=project_id)
            projdim.save()
        else:
            dimension = type_to_dimension[field_type].objects.get(pk=field)

        if field_type == "associatedorganization":
            dimension.value = Organization.objects.get(pk=value)
        elif field_type == "associatedperson":
            dimension.value = Person.objects.get(pk=value)
        elif field_type == "associatedpersons":
            person = Person.objects.get(pk=value)
            dimension.value.add(person)
        elif field_type == "associatedprojects":
            project = Project.objects.get(pk=value)
            dimension.value.add(project)
        elif field_type == "date":
            dimension.update_date(value)
        else:
            dimension.value = value
        dimension.save()

    #   Should actually handle PATCH but Django changes forms' patch requests
    #   to GET requests
    elif request.method == "GET":
        data = request.GET
        dimension = type_to_dimension[field_type].objects.get(pk=data.get('field'))
        value = data.get('value')
        if field_type == "associatedpersons":
            person = Person.objects.get(pk=value)
            dimension.value.remove(person)
        elif field_type == "associatedprojects":
            project = Project.objects.get(pk=value)
            dimension.value.remove(project)
        dimension.save()
    return redirect('show_project', project_id=project_id, permanent=True)


#   Import google sheet
#   TODO: Require admin
@login_required
def importer(request):
    if request.method == "POST":
        response_data = from_google_sheet(request.POST.get('url'))
        return HttpResponse(
            json_module.dumps(response_data),
            content_type="application/json"
        )
    elif request.method == "DELETE":
        GoogleSheet.objects.get(id=request.DELETE['sheet_id']).delete()
        response_data = {}
        response_data['result'] = 'Loaded sheet successfully!'
        response_data['name'] = google_sheet.name

        return HttpResponse(
            json_module.dumps(response_data),
            content_type="application/json"
        )


#   Gets all previously uploaded sheets and returns them in JSON
@require_GET
def get_sheets(request):
    if request.method == "GET":
        sheetObjects = GoogleSheet.objects.all()

        sheetsurls = []
        for s in sheetObjects:
            sheetsurls.append(s.name)
            sheetsurls.append(s.url)
        sheetJSON = json_module.dumps(sheetsurls)
        return HttpResponse(sheetJSON)
    return redirect('homepage')


def json(request):
    try:
        serializer = ProjectSerializer(Project.objects.all(), many=True)
        return JsonResponse(serializer.data, safe=False)
    except Exception as e:
        print("Error in JSON serialization: {}".format(e))


# site to see all projects, grouped by organization
@login_required
def projects(request):
    get_data_array()
    projects_all = Project.objects.all()

    projects_grouped = {}
    for org, ps in groupby(projects_all, lambda p: p.parent):
        projects_grouped[org] = []
        for p in ps:
            projects_grouped[org].append(p)


    dd = ContentType.objects.get_for_model(NumberDimension)
    number_dimensions = ProjectDimension.objects.filter(content_type=dd)
    budgets = []
    for num_dim in number_dimensions:
        if num_dim.dimension_object.name == "Budget":
            budgets.append(num_dim)

    response_data = {
        'projects': projects_all,
        'organizations': projects_grouped,
        'budgets':budgets
    }
    return render(request, 'projects.html', response_data)


# site to show datafields by organization
@login_required
def databaseview(request):
    if request.method == "POST":
        form = OrgForm(request.POST)
        if form.is_valid:
            add_field_form = ProjectTemplateForm()
            add_field_form.initial = {'organization': request.POST['orgs']}
            # (dimension name -> datatype) dictionary
            dims = {}
            organization = Organization.objects.get(pk=request.POST['orgs'])
            templates = organization.templates.all()
            if len(templates) > 0:
                template = templates[0]
                for t_dim in template.dimensions.all():
                    #TODO: group them by types to make the site easier to view?
                    t_dim_name = t_dim.content_type.model_class().__name__
                    dims[t_dim.name] = str(t_dim_name).replace("Dimension", "")
            # Group them by datatype
            defdict = {}
            for k,v in dims.items():
                defdict.setdefault(v, []).append(k)

            render_data = {
                'form':form,
                'dims':defdict,
                'add_field_form': add_field_form
            }
    elif request.user.is_superuser:
        add_field_form = ProjectTemplateForm()
        form = OrgForm()
        render_data = {
            'form':form,
            'add_field_form': add_field_form
        }
    else:
        try:
            organization = request.user.groups.first().employees.organization
        except:
            organization = request.user.groups.first().organizationadmins.organization
        add_field_form = ProjectTemplateForm()
        add_field_form.initial = {'organization': organization.pk}
        templates = organization.templates.all()
        dims = {}
        if len(templates) > 0:
            template = templates[0]
            for t_dim in template.dimensions.all():
                #TODO: group them by types to make the site easier to view?
                t_dim_name = t_dim.content_type.model_class().__name__
                dims[t_dim.name] = str(t_dim_name).replace("Dimension", "")
        # Group them by datatype
        defdict = {}
        for k,v in dims.items():
            defdict.setdefault(v, []).append(k)
        render_data = {
            'dims': defdict,
            'add_field_form': add_field_form
        }

    return render(request, 'database.html', render_data)


@login_required
def addproject(request):
    add_project_form = None
    add_project_form_prefix = 'add_project_form'
    if request.POST:
        add_project_form = AddProjectForm(request.POST, prefix=add_project_form_prefix)
    else:
        # Get initial values from referrering page that asked for project name and organization
        add_project_form = AddProjectForm(prefix='add_project_form')
        initial_data = {
            'name': request.GET.get('name'),
            'parent': request.GET.get('organization', ''),
            'organization': request.GET.get('organization', '')
        }
        add_project_form.initial = initial_data

    # Prevent user from chaning name or organization on "Add project" page.
    # If it were possible to change organization, every time organization selection is changed
    # organization project template must be reloaded to the page. Also the name field of project
    # instance should match the value of TextDimension with name 'Name'. Simpler implementation
    # when user is not allowed to change these values.
    add_project_form.disable_name_and_organization()

    forms = [add_project_form]

    try:
        form_prefix_parent = add_project_form.data.get(add_project_form_prefix+'-parent')
        pk = request.GET.get('organization', form_prefix_parent)
        organization = Organization.objects.get(pk=pk)
        templates = organization.templates.all()
        if len(templates) > 0:
            template = templates[0]
            for template_dimension in template.dimensions.all():
                td_modelname = template_dimension.content_type.model_class().__name__
                template_dimension_form_class = globals()[td_modelname+"Form"]
                # TODO: Should we check more carefully what is drawn from globals(). Security issue?
                template_dimension_form = template_dimension_form_class(
                    request.POST or None,
                    dimension_name = template_dimension.name,
                    project_form = add_project_form,
                    prefix = str(template_dimension.id)+'_form'
                )
                if template_dimension.name == 'Name':
                    value_field = template_dimension_form.fields['value']
                    value_field.widget = django.forms.HiddenInput()
                    value_field.initial = request.GET.get('name')
                forms.append(template_dimension_form)
    except Organization.DoesNotExist:
        pass

    forms_valid = True
    if request.POST:
        for form in forms:
            if not form.is_valid():
                forms_valid = False
        if forms_valid:
            for form in forms:
               form.save()
            return redirect('show_project', add_project_form.instance.id)

    return render(request, 'add_project.html', {'forms': forms})


# Gets all organizations and return them in a JSON string
def get_orgs(request):
    serializer = OrganizationSerializer(Organization.objects.all(), many=True)
    return JsonResponse(serializer.data, safe=False)


# Gets all persons and return them in a JSON string
def get_pers(request):
    serializer = PersonSerializer(Person.objects.all(), many=True)
    return JsonResponse(serializer.data, safe=False)


# Gets all projects and returns them with name and id in a JSON
def get_proj(request):
    serializer = ProjectNameIdSerializer(Project.objects.all(), many=True)
    return JsonResponse(serializer.data, safe=False)


@require_GET
def get(request, project_id):
    project = Project.objects.get(pk=project_id)
    ct = ContentType.objects.get_for_model(NumberDimension)

    existing = json_module.loads(request.GET.get('existing'))
    proj_dims = project.dimensions.filter(content_type=ct).exclude(id__in=existing)
    dims = {}
    for d in proj_dims:
        dims[d.id] = d.dimension_object.name

    return JsonResponse({'fields':dims})

#   Function that gets the value of a dimension that has multiple
#   items. Takes in the field type and the id of the dimension
@require_GET
def get_multiple(request, field_type, field_id):
    type_to_dimension = {
        'associatedpersons': AssociatedPersonsDimension,
        'associatedprojects': AssociatedProjectsDimension
    }
    value = type_to_dimension[field_type].objects.get(pk=field_id).value.all()
    data = [{'id': p.pk, 'name': str(p)} for p in value]
    return JsonResponse({'type': field_type, 'data': data})


def create_pathsnapshot(name, description, pid, x, y, start, end):
    p_snap = PathSnapshot()
    project = Project.objects.get(pk=project_id)
    p_snap.name = name
    p_snap.description = description
    p_snap.snap_type = 'PA'
    p_snap.project = pid
    p_snap.x = x
    p_snap.y = y
    p_snap.start_date = start
    p_snap.end_date = end
    p_snap.save()
    return p_snap


def create_fourfieldsnapshot(name, description, x, y, r, start, end, zoom):
    ff_snap = FourFieldSnapshot()
    ff_snap.name = name
    ff_snap.description = description
    ff_snap.snap_type = 'FF'
    ff_snap.x_dimension = x
    ff_snap.y_dimension = y
    ff_snap.radius_dimension = r
    ff_snap.start_date = start
    ff_snap.end_date = end
    ff_snap.zoom = zoom
    ff_snap.save()

    return ff_snap


@login_required
def snapshots(request, vis_type=None, snapshot_id=None):
    response_data = {}
    template = 'snapshots/error.html'

    #   Show all snapshots
    if not vis_type and not snapshot_id:
        snaps = []
        snap_types = Snapshot.get_subclasses()
        for snap_type in snap_types:
            snaps.extend(snap_type.objects.all())

        sorted_snaps = sorted(snaps, key=lambda snap: snap.created_at)
        sorted_snaps.reverse()
        response_data = {
            'snaps': sorted_snaps
        }
        template = 'snapshots/multiple/all.html'

    #   Show all snapshots of vis_type
    elif vis_type and not snapshot_id:
        if vis_type == 'path':
            snaps = PathSnapshot.objects.all()
            template = 'snapshots/multiple/path.html'
        elif vis_type == 'fourfield':
            snaps = FourFieldSnapshot.objects.all()
            template = 'snapshots/multiple/fourfield.html'

        response_data = {
            'snaps': snaps
        }

    #   Show a single snapshot
    elif vis_type and snapshot_id:
        try:
            if vis_type == 'path':
                snap = PathSnapshot.objects.get(pk=snapshot_id)
                name = snap.name
                desc = snap.description
                proj = snap.project
                x = snap.dimension_object_x
                y = snap.dimension_object_y
                serializer = ProjectSerializer(Project.objects.all(), many=True)
                data = json_module.dumps(serializer.data, cls=DjangoJSONEncoder)

                x = ProjectDimension.objects.get(
                    project=proj,
                    object_id=x.id,
                    content_type=snap.content_type_x
                )
                y = ProjectDimension.objects.get(
                    project=proj,
                    object_id=y.id,
                    content_type=snap.content_type_y
                )

                response_data = {
                    'name': name,
                    'description': desc,
                    'project': proj,
                    'x': x,
                    'y': y,
                    'data': data
                }
                template = 'snapshots/single/path.html'
            elif vis_type == 'fourfield':
                snap = FourFieldSnapshot.objects.get(pk=snapshot_id)
                name = snap.name
                desc = snap.description
                x = snap.x_dimension
                y = snap.y_dimension
                radius = snap.radius_dimension
                start_date = snap.start_date
                end_date = snap.end_date
                zoom = snap.zoom
                serializer = ProjectSerializer(Project.objects.all(), many=True)
                data = json_module.dumps(serializer.data, cls=DjangoJSONEncoder)

                response_data = {
                    'name': name,
                    'description': desc,
                    'x': x,
                    'y': y,
                    'radius': radius,
                    'start_date': start_date,
                    'end_date': end_date,
                    'zoom': zoom,
                    'data': data
                }
                template = 'snapshots/single/fourfield.html'
        except Exception as e:
            print("ERROR: {}".format(e))
            pass

    #   Render the appropriate template
    return render(request, template, response_data)


@login_required
def create_snapshot(request):
    if request.method == 'POST':
        snapshot_type = request.POST['type']
        if snapshot_type == 'path':

            name = request.POST['name']
            description = request.POST['description']
            pid = request.POST['project_id']
            x = request.POST['x_dim']
            y = request.POST['y_dim']
            start_ddmmyyyy = request.POST['start-date']
            end_ddmmyyyy = request.POST['end-date']
            start = dt.datetime.strptime(start_ddmmyyyy, "%d/%m/%Y").strftime("%Y-%m-%d")
            end = dt.datetime.strptime(end_ddmmyyyy, "%d/%m/%Y").strftime("%Y-%m-%d")

            p_snap = create_pathsnapshot(
                        name=name,
                        description=description,
                        pid = pid,
                        #x = x,
                        y = y,
                        start = start,
                        end = end
                    )
            url = 'snapshots/path/{}'.format(p_snap.id)
            return redirect(url, permanent=True)
        elif snapshot_type == 'fourfield':
            x = request.POST['x_dim']
            y = request.POST['y_dim']
            r = request.POST['r_dim']
            start_ddmmyyyy = request.POST['start-date']
            end_ddmmyyyy = request.POST['end-date']

            name = request.POST['name']
            description = request.POST['description']
            start = dt.datetime.strptime(start_ddmmyyyy, "%d/%m/%Y").strftime("%Y-%m-%d")
            end = dt.datetime.strptime(end_ddmmyyyy, "%d/%m/%Y").strftime("%Y-%m-%d")
            zoom = request.POST['zoom']

            ff_snap = create_fourfieldsnapshot(
                        name=name,
                        description=description,
                        x=x,
                        y=y,
                        r=r,
                        start=start,
                        end=end,
                        zoom=zoom
                    )
            url = 'snapshots/fourfield/{}'.format(ff_snap.id)
            return redirect(url, permanent=True)
        else:
            pass
