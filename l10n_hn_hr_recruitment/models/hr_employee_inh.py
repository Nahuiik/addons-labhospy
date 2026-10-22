# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, _lt, api, fields, models
from odoo.exceptions import UserError

LIVES_WITH = [('his_parent', 'His parents'),
              ('his_family', 'His family'),
              ('his_relative', 'His relatives'),
              ('alone', 'Alone')]

DEPENDENT_PEOPLE = [('son', 'Sons'),
                    ('spouse', 'Spouse'),
                    ('parent', 'Parents'),
                    ('other', 'Others')]
HAS_LICENSE = [('yes', 'Yes'),
               ('not', 'No')]

HEALTH_STATUS = [('good', 'Good'),
                 ('regular', 'Regular'),
                 ('bad', 'Bad')
                 ]
CHRONIC_ILLNESS = [('yes', 'Yes'),
               ('not', 'No')]

AVAILABLE_PRIORITIES = [
    ('0', 'Normal'),
    ('1', 'Good'),
    ('2', 'Very Good'),
    ('3', 'Excellent')
]

def _sanitize_field_selection(field):
    """Cast selection keys/labels to strings to satisfy registry validation."""
    if not field or not isinstance(field.selection, list):
        return
    sanitized = []
    for option in field.selection:
        if not isinstance(option, (list, tuple)) or not option:
            continue
        parts = list(option)
        if not isinstance(parts[0], str):
            parts[0] = str(parts[0])
        if len(parts) > 1 and parts[1] is not None and not isinstance(parts[1], str):
            parts[1] = str(parts[1])
        sanitized.append(tuple(parts))
    field.selection = sanitized

class employeeInh(models.Model):
    _inherit = "hr.employee"

    stage_id = fields.Many2one('hr.recruitment.stage', 'Stage')
    application_count = fields.Integer(help='Applications with the same email')
    meeting_count = fields.Integer(help='Meeting Count')
    kanban_state = fields.Selection([
        ('normal', 'Grey'),
        ('done', 'Green'),
        ('blocked', 'Red')], string='Kanban State',
        copy=False, default='normal', required=True)
    legend_normal = fields.Char(
        'Grey Kanban Label', default=lambda self: _('In Progress'))
    legend_blocked = fields.Char(
        'Red Kanban Label', default=lambda self: _('Blocked'))
    legend_done = fields.Char(
        'Green Kanban Label', default=lambda self: _('Ready for Next Stage'))
    partner_name = fields.Char("Applicant's Name")
    partner_id = fields.Many2one('res.partner', 'Customer')
    refuse_reason_id = fields.Many2one('hr.applicant.refuse.reason', string='Refuse Reason', tracking=True)
    email_from = fields.Char("Applicant Email", size=128, help="Email provided by the applicant", store=True)
    email_cc = fields.Char('Email cc', help='List of cc from incoming emails.')
    partner_phone = fields.Char("Applicant Phone", size=32, store=True)
    partner_mobile = fields.Char("Applicant Mobile", size=32, store=True)
    type_id = fields.Many2one('hr.recruitment.degree', "Degree")
    categ_ids = fields.Many2many('hr.applicant.category', string="Applicant Tags")
    priority = fields.Selection(AVAILABLE_PRIORITIES, "Appreciation", default='0')
    medium_id = fields.Many2one('utm.medium', readonly=True)
    source_id = fields.Many2one('utm.source', "Source", ondelete='cascade')
    salary_expected = fields.Float("Expected Salary", aggregator="avg", help="Salary Expected by Applicant", tracking=True)
    salary_expected_extra = fields.Char("Expected Salary Extra", help="Salary Expected by Applicant, extra advantages", tracking=True)
    salary_expected_max = fields.Float("Salario Esperado (max)", aggregator="avg", help="Salary Expected by Applicant", tracking=True)
    salary_proposed = fields.Float("Proposed Salary", aggregator="avg", help="Salary Proposed by the Organisation", tracking=True)
    salary_proposed_extra = fields.Char("Proposed Salary Extra", help="Salary Proposed by the Organisation, extra advantages", tracking=True)
    availability = fields.Date("Availability", help="The date at which the applicant will be available to start working", tracking=True)
    emp_id = fields.Many2one('hr.employee', string="Linked Employee", help="Employee linked to the applicant.", copy=False)
    name_father = fields.Char(string='Father Name')
    address_father = fields.Char(string='Father Address')
    name_mother = fields.Char(string='Mother Name')
    address_mother = fields.Char(string='Mother Address')
    occupation_mother = fields.Char(string='Mother Occupation')
    occupation_father = fields.Char(string='Father Occupation')
    name_wife = fields.Char(string='Spouse Name')
    address_wife = fields.Char(string='Spouse Address')
    occupation_wife = fields.Char(string='Spouse Occupation')
    son_name_age = fields.Text(string='Sons Name and Age')
    study_current = fields.Char(string='Current Study')
    school_study_current = fields.Char(string='School Study Current')
    work_calendar = fields.Char(string='Work Calendar')
    course_carrera = fields.Char(string='Course and Carrera')
    grade = fields.Char(string='Grade')
    description = fields.Char(string='Description')

    photo = fields.Binary(string="Photo")
    age = fields.Integer(string="Age", compute='_compute_age', compute_sudo=True)
    birth_date = fields.Date(string="Birth Date")
    street = fields.Char(string='Street')
    phone2 = fields.Char(string='Movil')
    due_date_license = fields.Date(string='Fecha de Vencimiento Licencia')
    street2 = fields.Char(string='Street2')
    zip = fields.Char(string='Zip')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string="State")
    hn_country_id = fields.Many2one('res.country', string="Country (address)")
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender (Recruitment)', default="male", tracking=True)
    marital = fields.Selection([
        ('single', 'Soltero'),
        ('married', 'Casado(a)'),
        ('cohabitant', 'Union Libre'),
        ('widower', 'Viudo(a)'),
        ('divorced', 'Divorciado(a)'),
        ('other', 'Otro'),
    ], string='Marital Status', default='single', tracking=True)
    marital_status_id = fields.Many2one(
        'l10n_hn_hr_recruitment.marital.status',
        string='Estado civil',
        tracking=True,
        ondelete='restrict',
    )

    private_emails = fields.Char(string="Correo electrónico")
    others_marital = fields.Char(string='Marital Status Other')
    identification_id = fields.Char(string='Identification No', size=13, tracking=True)
    passport_id = fields.Char('Passport No', tracking=True)
    insurance_id = fields.Char('Insurance No', tracking=True)
    rtn = fields.Char('RTN', tracking=True)
    place_of_birth = fields.Char('Place of Birth',  tracking=True)
    nationality_id = fields.Many2one('res.country', string="Nationality Country",
                                       tracking=True)
    live_with = fields.Selection(LIVES_WITH, string='Lives with')
    height = fields.Float(string='Height')
    weight = fields.Float(string='Weight')
    dependent_people = fields.Many2many('l10n_hn_hr_recruitment.dependents_person', string='Dependent')
    has_license = fields.Selection(HAS_LICENSE, string="Has licence?",default="not")
    class_license = fields.Selection(
        [
            # Valores alineados a SERTRACEN / importación (etiquetas en español)
            ("particular", "Particular"),
            ("liviana", "Liviana"),
            ("motociclistas", "Motociclistas"),
            # Claves históricas (datos ya guardados / plantillas en inglés)
            ("light", "Light"),
            ("heavy", "Heavy"),
            ("moto", "Motocicleta"),
            ("international", "International"),
        ],
        string="Tipo de Licencia",
    )
    number_license = fields.Char(string='Licence Number')
    document_work = fields.Char(string='Work Document')
    health_status = fields.Selection(HEALTH_STATUS, string='Health Status')
    chronic_illness = fields.Selection(CHRONIC_ILLNESS, string='Chronic Illness',default="not")
    chronic_illness_observation = fields.Char(string='Explicate')
    practice_sport = fields.Selection(CHRONIC_ILLNESS, string='To Practice Sports',default='not')
    sport_ids = fields.Many2many('hr.sport', 'hr_employee_sport_rel', 'employee_id', 'sport_id', string="Sports")
    club_social_deport = fields.Selection(CHRONIC_ILLNESS, string='Club Social or Deport',default='not')
    social_club_ids = fields.Many2many('l10n_hn_hr_recruitment.social_club',string="Clubs")
    favorite_hobby = fields.Char(string='Favorite Hobby')
    language_ids = fields.One2many('res.lang.other', 'employee_id', string='Languages')
    department_function = fields.Char(string='Department Function')
    work_other = fields.Char(string='Works Other')
    software = fields.Char(string='Software')
    machine = fields.Char(string='Machine')
    study_field_id = fields.Many2one(
        'l10n_hn_hr_recruitment.field.of.study',
        string='Campo de estudio',
        groups='hr.group_hr_user',
        ondelete='set null',
    )
    doc_ids = fields.One2many("l10n_hn_hr_recruitment.docs_employee","employee_id", string="Docs Employee")
    doc_diseases_ids = fields.One2many("l10n_hn_hr_recruitment.docs_diseases","employee_id", string="Registro de Enfermedades")
    bank_name = fields.Char(string="Primary Bank")
    bank_names = fields.Char(compute='_get_bank_name', string="Main Bank")
    bank_account_hover = fields.Char(compute='_get_bank_account_hover', string="Code bank")
    municipality = fields.Char(string="Municipality")
    spouse = fields.Char(string="Spouse")
    family_information_id = fields.One2many('l10n_hn_hr_recruitment.family_information','employee_id',string="Family Information")
    academic_training_id = fields.One2many('l10n_hn_hr_recruitment.academic_formation','employee_id',string="Academic Training")
    other_courses_id = fields.One2many('l10n_hn_hr_recruitment.other_courses','employee_id',string="Other Courses")
    area_id = fields.Many2one('l10n_hn_hr_recruitment.areas',string="Area")
    certificate_id = fields.Many2one('l10n_hn_hr_recruitment.grade_certificate',string="Nivel de Certificado")
    surgery_ids = fields.Many2many('hr.surgery', 'hr_employee_surgery_rel', 'employee_id', 'surgery_id', string="Cirugías")
    diseases_ids = fields.Many2many('hr.disease', string='Diseases He Suffers')
    medication_ids = fields.Many2many('hr.medication', 'hr_employee_medication_rel', 'employee_id', 'medication_id', string="Medicamentos")
    continuo_medication = fields.Selection(string='Medicamentos de uso continuo', selection=[('yes', 'Si'), ('no', 'No'),], default='no')
    birthplace = fields.Char(string='')
    postal_code = fields.Char(string='')
    current_address = fields.Char(string='')
    number_employee = fields.Char("Numero personal del empleado")
    number_emergency2 = fields.Char("Teléfono Emergencia 2")
    name_emergency = fields.Char("Contacto de Emergencia 2")
    reference_point = fields.Char("Reference Point")
    relation_emergency = fields.Char("Emergency Reference 1")
    relation_emergency2 = fields.Char("Emergency Reference 2")
    relation_emergency_id = fields.Many2one('l10n_hn_hr_recruitment.family_relation', string="Relacion")
    relation_emergency_2_id = fields.Many2one('l10n_hn_hr_recruitment.family_relation', string="Relacion 2")
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string='Registro Enfermedades',
        help="Adjunta documentos relacionados incapacidades, cirugias, registros de enfermedades, etc."
    )
    address_home = fields.Char(string="Dirección")

    @api.depends('bank_account_ids.bank_id', 'salary_distribution')
    def _get_bank_name(self):
        for rec in self:
            account = rec.primary_bank_account_id or rec.bank_account_ids[:1]
            rec.bank_names = account.bank_id.name if account and account.bank_id else ''


    @api.depends('bank_account_ids.acc_number', 'salary_distribution')
    def _get_bank_account_hover(self):
        for rec in self:
            account = rec.primary_bank_account_id or rec.bank_account_ids[:1]
            number = account.acc_number if account else False
            if not number:
                rec.bank_account_hover = ''
                continue
            if len(number) <= 4:
                rec.bank_account_hover = number
                continue
            masked = f"{'*' * (len(number) - 4)}{number[-4:]}"
            rec.bank_account_hover = masked

    @api.model
    def _prepare_marital_vals(self, vals):
        vals = dict(vals)
        Marital = self.env['l10n_hn_hr_recruitment.marital.status']
        if vals.get('marital_status_id'):
            ms = Marital.browse(vals['marital_status_id'])
            if ms and ms.code:
                vals['marital'] = ms.code
        elif vals.get('marital') is not False and vals.get('marital') is not None and not vals.get('marital_status_id'):
            ms = Marital.search([('code', '=', vals['marital'])], limit=1)
            if ms:
                vals['marital_status_id'] = ms.id
        return vals

    @api.model
    def _prepare_study_field_vals(self, vals):
        vals = dict(vals)
        F = self.env['l10n_hn_hr_recruitment.field.of.study']
        if vals.get('study_field_id'):
            rec = F.browse(vals['study_field_id'])
            if rec:
                vals['study_field'] = rec.name
        elif vals.get('study_field'):
            text = (vals.get('study_field') or '').strip()
            if text and not vals.get('study_field_id'):
                rec = F.search([('name', '=ilike', text)], limit=1)
                if rec:
                    vals['study_field_id'] = rec.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        out = []
        for v in vals_list:
            v2 = self._prepare_study_field_vals(dict(v))
            out.append(self._prepare_marital_vals(v2))
        return super().create(out)

    def write(self, vals):
        vals = self._prepare_study_field_vals(dict(vals))
        vals = self._prepare_marital_vals(vals)
        return super().write(vals)

    @api.onchange('study_field_id')
    def _onchange_study_field_id(self):
        if self.study_field_id:
            self.study_field = self.study_field_id.name

    @api.constrains('identification_id')
    def _check_identification_id(self):
        for rec in self:
            if rec.identification_id:
                if not rec.identification_id.isdigit() or len(rec.identification_id) != 13:
                    raise UserError('El número de identidad debe contener exactamente 13 dígitos numéricos.')
                existing_employee = rec.search([('identification_id', '=', rec.identification_id), ('id', '!=', rec.id)])
                if existing_employee:
                    raise UserError('El número de identidad ya existe. Debe ser único.')

    @api.depends('birth_date')
    def _compute_age(self):
        for obj in self:
            if obj.birth_date:
                obj.age = relativedelta(date.today(), obj.birth_date).years
            else:
                obj.age = 0

    @classmethod
    def _setup_complete(cls):
        super()._setup_complete()
        _sanitize_field_selection(cls._fields.get('class_license'))

class HrVersion(models.Model):
    _inherit = "hr.version"

    doc_ids = fields.One2many(
        "l10n_hn_hr_recruitment.docs_contract",
        "contract_id",
        string="Contract Documents",
    )

class docsContract(models.Model):
    _name = "l10n_hn_hr_recruitment.docs_contract"
    _description = "Recruitment Contract Documents"

    contract_id = fields.Many2one("hr.version", string="Contract Record")
    name = fields.Char(string="Descripción")
    document = fields.Binary(string="Documento", attachment=True)  
    store_fname = fields.Char(string="File Name")
    attachment_url = fields.Char(compute="_compute_attachment_url")
    show_pdf = fields.Boolean(string="Mostrar PDF", default=False)  # Nuevo campo

    def toggle_pdf_view(self):
        """ Alternar la visibilidad del visor de PDF """
        for record in self:
            record.show_pdf = not record.show_pdf

    def _compute_attachment_url(self):
        for record in self:
            record.attachment_url = False


class docsEmployee(models.Model):
    _name = "l10n_hn_hr_recruitment.docs_employee"
    _description = "Recruitment Employee Documents"

    employee_id = fields.Many2one("hr.employee", string="Employee")
    applicant_id = fields.Many2one('hr.applicant', string='Applicant', ondelete='cascade')
    name = fields.Char(string="Description")
    document = fields.Binary(string="Document",attachment=True)  
    store_fname = fields.Char(string="File Name")

class docsDiaseases(models.Model):
    _name = "l10n_hn_hr_recruitment.docs_diseases"
    _description = "Recruitment Disease Documents"

    employee_id = fields.Many2one("hr.employee", string="Employee")
    diseases_id = fields.Many2one('hr.disease', string='Enfermedad')
    name = fields.Char(string="Description")
    claim = fields.Char(string="Proceso de Reclamo")
    observation = fields.Char(string="Observación")
    date = fields.Date(string="Fecha")
    document = fields.Binary(string="Document",attachment=True)  
    store_fname = fields.Char(string="File Name")



class dependentsPersons(models.Model):
    _name = 'l10n_hn_hr_recruitment.dependents_person'
    _description = "Recruitment Dependent Person"

    name = fields.Char("Name")
    color = fields.Integer('Color Index',default=3)

class familyInformation(models.Model):
    _name = 'l10n_hn_hr_recruitment.family_information'
    _description = "Recruitment Family Information"

    name = fields.Char(string='Name')
    employee_id = fields.Many2one('hr.employee',string="Employee")
    relation = fields.Many2one('l10n_hn_hr_recruitment.family_relation',string="Relation")
    domicile = fields.Char(string="Domicile")
    ocupation = fields.Char(string="Ocupation")
    age = fields.Integer(string="Age")

class academicFormation(models.Model):
    _name = 'l10n_hn_hr_recruitment.academic_formation'
    _description = "Recruitment Academic Formation"

    name = fields.Selection([
                            ('1', 'Primary'),
                            ('2', 'Secondary or Vocational'),
                            ('3', 'Preparatory or Vocational'),
                            ('4', 'University'),
                            ('5', 'Postgraduate'),
                            ('6', 'Other'),
                        ],string="Name")
    applicant_id = fields.Many2one('hr.applicant', string='Applicant', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee',string="Employee")
    address = fields.Char(string="Address")
    date_from  = fields.Date(string="From")
    date_to = fields.Date(string="To")
    title_received = fields.Char(string="Title Received")
    field_of_study_id = fields.Many2one(
        'l10n_hn_hr_recruitment.field.of.study',
        string='Campo de estudio',
        ondelete='set null',
    )

    @classmethod
    def _setup_complete(cls):
        super()._setup_complete()
        _sanitize_field_selection(cls._fields.get('name'))

class othersCourses(models.Model):
    _name = 'l10n_hn_hr_recruitment.other_courses'
    _description = "Recruitment Other Courses"

    study_center = fields.Char(string="Study Center")
    employee_id = fields.Many2one('hr.employee',string="Employee")
    schedule = fields.Char(string="Schedule")
    course = fields.Char(string="Course or career")
    grade = fields.Char(string="Grade")

class areas(models.Model):
    _name = 'l10n_hn_hr_recruitment.areas'
    _description = "Recruitment Area"

    name = fields.Char(string="Name")

class RecruitmentFamilyRelation(models.Model):
    _name = 'l10n_hn_hr_recruitment.family_relation'
    _description = "Recruitment Family Relation"

    name = fields.Char(string="Relation")

class RecruitmentGradeCertificate(models.Model):
    _name = 'l10n_hn_hr_recruitment.grade_certificate'
    _description = "Recruitment Grade Certificate"

    name = fields.Char(string="Certificado")
    

class RecruitmentSocialClub(models.Model):
    _name = 'l10n_hn_hr_recruitment.social_club'
    _description = "Recruitment Social Club"

    name = fields.Char(string="Name")
    color = fields.Integer('Color Index',default=1)
