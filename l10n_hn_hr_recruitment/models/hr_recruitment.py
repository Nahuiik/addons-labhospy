# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

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

class Company(models.Model):
    _inherit = "res.company"

    numero = fields.Char(string='Id', help='(1 Postensa), (2 Concremix), (3 Credipro)')

class Applicant(models.Model):
    _inherit = "hr.applicant"

    photo = fields.Binary(string="Photo")
    age = fields.Integer(string="Age", compute='_compute_age', compute_sudo=True)
    birth_date = fields.Date(string="Birth Date")
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    zip = fields.Char(string='Zip')
    city = fields.Char(string='City')
    salary_expected_max = fields.Float("Salario Esperado (max)", aggregator="avg", help="Salary Expected by Applicant", tracking=True)
    state_id = fields.Many2one('res.country.state', string="State")
    country_id = fields.Many2one('res.country', string="Country")
    gender = fields.Selection([
        ('male',  'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], default="male", tracking=True)
    marital = fields.Selection([
        ('single', 'Soltero(a)'),
        ('married', 'Casado(a)'),
        ('cohabitant', 'Unión libre'),
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
    others_marital = fields.Char(string='Marital Status Other')
    identification_id = fields.Char(string='Identification No', tracking=True)
    passport_id = fields.Char('Passport No', tracking=True)
    insurance_id = fields.Char('Insurance No', tracking=True)
    rtn = fields.Char('RTN', tracking=True)
    place_of_birth = fields.Char('Place of Birth',  tracking=True)
    nationality_id = fields.Many2one('res.country', string="Nationality (Country)",
                                       tracking=True)
    live_with = fields.Selection(LIVES_WITH, string='Lives with')
    height = fields.Float(string='Height')
    weight = fields.Float(string='Weight')
    dependent_people = fields.Selection(DEPENDENT_PEOPLE, string='Dependent People')
    has_license = fields.Selection(HAS_LICENSE, string="Has licence?")
    class_license = fields.Char(string='Class')
    number_license = fields.Char(string='Number')
    document_work = fields.Char(string='Work Document')
    health_status = fields.Selection(HEALTH_STATUS, string='Health Status')
    chronic_illness = fields.Selection(CHRONIC_ILLNESS, string='Chronic Illness')
    chronic_illness_observation = fields.Char(string='Observation')
    practice_sport = fields.Selection(CHRONIC_ILLNESS, string='To Practice Sports')
    sport_ids = fields.Many2many('hr.sport', string="Sports")
    club_social_deport = fields.Selection(CHRONIC_ILLNESS, string='Club Social or Deport')
    social_club_ids = fields.Many2many('l10n_hn_hr_recruitment.social_club', string="Clubs")
    favorite_hobby = fields.Char(string='Favorite Hobby')
    name_father = fields.Char(string='Father Name')
    address_father = fields.Char(string='Father Address')
    occupation_father = fields.Char(string='Father Occupation')
    name_mother = fields.Char(string='Mother Name')
    address_mother = fields.Char(string='Mother Address')
    occupation_mother = fields.Char(string='Mother Occupation')
    name_wife = fields.Char(string='Spouse Name')
    address_wife = fields.Char(string='Spouse Address')
    occupation_wife = fields.Char(string='Spouse Occupation')
    son_name_age = fields.Text(string='Sons Name and Age')

    primary_school = fields.Char(string='Primary School')
    primary_school_address = fields.Char(string='Primary School Address')
    primary_school_from = fields.Date(string='Primary From')
    primary_school_to = fields.Date(string='Primary To')
    primary_school_year = fields.Char(string='Primary Years')
    primary_school_title = fields.Char(string='Primary Title')

    secondary_school = fields.Char(string='Secondary School')
    secondary_school_address = fields.Char(string='Secondary School Address')
    secondary_school_from = fields.Date(string='Secondary From')
    secondary_school_to = fields.Date(string='Secondary To')
    secondary_school_year = fields.Char(string='Secondary Years')
    secondary_school_title = fields.Char(string='Secondary Title')

    vocational_school = fields.Char(string='Vocational School')
    vocational_school_address = fields.Char(string='Vocational School Address')
    vocational_school_from = fields.Date(string='Vocational From')
    vocational_school_to = fields.Date(string='Vocational To')
    vocational_school_year = fields.Char(string='Vocational Years')
    vocational_school_title = fields.Char(string='Vocational Title')

    university_school = fields.Char(string='University')
    university_school_address = fields.Char(string='University Address')
    university_school_from = fields.Date(string='University From')
    university_school_to = fields.Date(string='University To')
    university_school_year = fields.Char(string='University Years')
    university_school_title = fields.Char(string='University Title')

    post_grade_school = fields.Char(string='Postgraduate')
    post_grade_school_address = fields.Char(string='Postgraduate Address')
    post_grade_school_from = fields.Date(string='Postgraduate From')
    post_grade_school_to = fields.Date(string='Postgraduate To')
    post_grade_school_year = fields.Char(string='Postgraduate Years')
    post_grade_school_title = fields.Char(string='Postgraduate Title')
    study_current = fields.Char(string='Current Study')
    school_study_current = fields.Char(string='School Study Current')
    work_calendar = fields.Char(string='Work Calendar')
    course_carrera = fields.Char(string='Course and Carrera')
    grade = fields.Char(string='Grade')

    language_ids = fields.One2many('res.lang.other', 'applicant_id', string='Languages')
    department_function = fields.Char(string='Department Function')
    work_other = fields.Char(string='Works Other')
    software = fields.Char(string='Software')
    machine = fields.Char(string='Machine')
    municipality = fields.Char(string="Municipalidad")
    doc_ids = fields.One2many("l10n_hn_hr_recruitment.docs_employee","applicant_id", string="Docs Aplicant")
    family_information_id = fields.One2many('l10n_hn_hr_recruitment.family_information','employee_id',string="Family Information")
    academic_training_id = fields.One2many('l10n_hn_hr_recruitment.academic_formation','applicant_id',string="Academic Training")
    other_courses_id = fields.One2many('l10n_hn_hr_recruitment.other_courses','employee_id',string="Other Courses")
    area_id = fields.Many2one('l10n_hn_hr_recruitment.areas',string="Area")
    certificate_id = fields.Many2one('l10n_hn_hr_recruitment.grade_certificate',string="Nivel de Certificado")
    surgery_ids = fields.Many2many('hr.surgery', string="Cirugías")
    number_emergency2 = fields.Char("Teléfono Emergencia 2")
    emergency_contact = fields.Char("Contacto de Emergencia")
    emergency_phone = fields.Char("Teléfono Emergencia")
    name_emergency = fields.Char("Contacto de Emergencia 2")
    relation_emergency_id = fields.Many2one('l10n_hn_hr_recruitment.family_relation', string="Relacion")
    relation_emergency_2_id = fields.Many2one('l10n_hn_hr_recruitment.family_relation', string="Relacion 2")
    stage_sequence = fields.Integer(
        string='Stage Sequence',
        related='stage_id.sequence',
        store=True,
        readonly=True,
    )
    line_ids = fields.One2many('hr.recruitment.stage.checklist.line', 'applicant_id', string="Lineas de Verificación")
    survey_id = fields.Many2one(
        'survey.survey',
        string="Entrevista",
        compute='_compute_survey_id',
        readonly=True,
    )

    def action_show_survey_url(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('URL de la entrevista'),
            'res_model': 'hr.applicant.survey.url.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
        }

    @api.depends('stage_id.survey_id', 'job_id.survey_id')
    def _compute_survey_id(self):
        for applicant in self:
            if applicant.stage_id and applicant.stage_id.survey_id:
                applicant.survey_id = applicant.stage_id.survey_id
            elif applicant.job_id and applicant.job_id.survey_id:
                applicant.survey_id = applicant.job_id.survey_id
            else:
                applicant.survey_id = False

    missing_checklist_line_names = fields.Html(
        compute='_compute_missing_checklist_line_names',
        string='Verificaciones pendientes',
    )

    @api.depends('line_ids.is_required', 'line_ids.necessary', 'line_ids.stage_id', 'stage_id')
    def _compute_missing_checklist_line_names(self):
        for applicant in self:
            if not applicant.stage_id:
                applicant.missing_checklist_line_names = False
                continue
            current_stage_lines = applicant.line_ids.filtered(
                lambda l: l.stage_id and l.stage_id == applicant.stage_id
            )
            missing = current_stage_lines.filtered(lambda l: l.is_required and not l.necessary)
            if missing:
                items = ''.join(f'<li>{name}</li>' for name in missing.mapped('name'))
                applicant.missing_checklist_line_names = f'''
                    <div class="alert alert-warning mb-0" role="alert">
                        <strong>No puedes cambiar de etapa:</strong> Completa las siguientes verificaciones obligatorias en la pestaña Checklist:
                        <ul class="mb-0 mt-2">{items}</ul>
                    </div>
                '''
            else:
                applicant.missing_checklist_line_names = False

    def _prepare_applicant_marital_vals(self, vals):
        vals = dict(vals)
        Marital = self.env['l10n_hn_hr_recruitment.marital.status']
        if vals.get('marital_status_id'):
            ms = Marital.browse(vals['marital_status_id'])
            if ms and ms.code:
                vals['marital'] = ms.code
        elif vals.get('marital') is not False and vals.get('marital') is not None and not vals.get('marital_status_id'):
            code = vals['marital'] if vals['marital'] != 'others' else 'other'
            ms = Marital.search([('code', '=', code)], limit=1)
            if ms:
                vals['marital_status_id'] = ms.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._prepare_applicant_marital_vals(dict(v)) for v in vals_list]
        applicants = super().create(vals_list)
        for applicant, vals in zip(applicants, vals_list):
            stage_id = vals.get('stage_id') or applicant.stage_id.id
            if stage_id:
                applicant._generate_checklist_lines(stage_id)
        return applicants

    def write(self, vals):
        vals = self._prepare_applicant_marital_vals(dict(vals))
        if 'stage_id' in vals:
            for applicant in self:
                applicant._ensure_checklist_completion(vals)
        res = super().write(vals)
        if 'stage_id' in vals:
            for applicant in self:
                if applicant.stage_id:
                    applicant._generate_checklist_lines(applicant.stage_id.id)
        return res

    def _ensure_checklist_completion(self, vals=None):
        self.ensure_one()
        if not self.stage_id:
            return
        vals = vals or {}
        # Construir necessary efectivo: usar vals si hay actualizaciones de line_ids
        line_updates = {}
        for cmd in vals.get('line_ids', []):
            if cmd[0] == 1 and len(cmd) >= 3:  # (1, id, {vals})
                line_updates[cmd[1]] = cmd[2]
        current_stage_lines = self.line_ids.filtered(
            lambda l: l.stage_id and l.stage_id == self.stage_id
        )
        missing_lines = self.env['hr.recruitment.stage.checklist.line']
        for line in current_stage_lines:
            if not line.is_required:
                continue
            necessary = line.necessary
            if line.id in line_updates and 'necessary' in line_updates[line.id]:
                necessary = line_updates[line.id]['necessary']
            if not necessary:
                missing_lines |= line
        if missing_lines:
            names = ', '.join(missing_lines.mapped('name'))
            raise UserError(
                _("No puedes cambiar de etapa porque hay verificaciones obligatorias sin completar: %s", names)
            )

    def _generate_checklist_lines(self, stage_id):
        self.ensure_one()
        StageChecklist = self.env['hr.recruitment.stage.checklist']
        StageChecklistLine = self.env['hr.recruitment.stage.checklist.line']
        existing_lines = StageChecklistLine.search([
            ('applicant_id', '=', self.id),
            ('stage_id', '=', stage_id),
        ], limit=1)
        if existing_lines:
            return
        checklists = StageChecklist.search([('stage_id', '=', stage_id)])
        for checklist in checklists:
            checklist._create_lines_for_applicant(self)

    @api.depends('birth_date')
    def _compute_age(self):
        for obj in self:
            if obj.birth_date:
                obj.age = relativedelta(date.today(), obj.birth_date).years
            else:
                obj.age = 0

    def create_employee_from_applicant(self):
        """Create an employee from the applicant and copy custom data."""
        action = super().create_employee_from_applicant()
        employee_id = action.get('res_id')
        if not employee_id:
            return action
        employee = self.env['hr.employee'].browse(employee_id)
        if not employee:
            return action

        values_to_write = {
            'photo': self.photo,
            'birth_date': self.birth_date,
            'street': self.street,
            'street2': self.street2,
            'zip': self.zip,
            'city': self.city,
            'state_id': self.state_id.id,
            'hn_country_id': self.country_id.id if self.country_id else False,
            'gender': self.gender,
            'marital_status_id': self.marital_status_id.id,
            'marital': self.marital_status_id.code if self.marital_status_id else self.marital,
            'others_marital': self.others_marital,
            'identification_id': self.identification_id,
            'passport_id': self.passport_id,
            'insurance_id': self.insurance_id,
            'rtn': self.rtn,
            'place_of_birth': self.place_of_birth,
            'nationality_id': self.nationality_id.id,
            'live_with': self.live_with,
            'height': self.height,
            'weight': self.weight,
            'has_license': self.has_license,
            'class_license': self.class_license,
            'number_license': self.number_license,
            'document_work': self.document_work,
            'department_function': self.department_function,
            'work_other': self.work_other,
            'software': self.software,
            'machine': self.machine,
            'area_id': self.area_id.id,
            'certificate_id': self.certificate_id.id,
            'number_emergency2': self.number_emergency2,
            'emergency_contact': self.emergency_contact,
            'emergency_phone': self.emergency_phone,
            'name_emergency': self.name_emergency,
            'relation_emergency_id': self.relation_emergency_id.id,
            'relation_emergency_2_id': self.relation_emergency_2_id.id,
        }
        m2m_values = {
            'surgery_ids': [(6, 0, self.surgery_ids.ids)],
            'sport_ids': [(6, 0, self.sport_ids.ids)],
            'social_club_ids': [(6, 0, self.social_club_ids.ids)],
        }
        values_to_write.update({key: val for key, val in m2m_values.items() if val})
        cleaned_values = {key: value for key, value in values_to_write.items() if value not in (False, None)}
        if cleaned_values:
            employee.write(cleaned_values)

        self.doc_ids.write({'employee_id': employee.id})
        self.family_information_id.write({'employee_id': employee.id})
        self.academic_training_id.write({'employee_id': employee.id})
        self.other_courses_id.write({'employee_id': employee.id})
        self._gn_recruitment_core_copy_curriculum_to_employee(employee)

        if self.language_ids:
            language_commands = [
                (0, 0, {
                    'lang_id': lang.lang_id,
                    'level': lang.level,
                }) for lang in self.language_ids
            ]
            employee.write({'language_ids': [(5, 0, 0)] + language_commands})
        return action


class ResLangOther(models.Model):
    _name = 'res.lang.other'
    _description = 'Description'

    applicant_id = fields.Many2one('hr.applicant', string='Applicant', ondelete='cascade')
    employee_id  = fields.Many2one('hr.employee', string='Employee', ondelete='cascade')
    lang_id = fields.Char(string='Language')
    level = fields.Selection([
                                ('level_50', '50 %'),
                                ('level_75', '75 %'),
                                ('level_100', '100 %'),
                              ])


class StageChecklist(models.Model):
    _name = 'hr.recruitment.stage.checklist'
    _description = 'Lista de Verificación'

    _order = "stage_id asc, id desc"

    sequence = fields.Integer('Sequencia', related='stage_id.sequence')
    line_ids = fields.One2many('hr.recruitment.stage.checklist.line', 'checklist_id', string="Lineas de Verificación")
    name = fields.Char(string='Name', store=True)
    stage_id = fields.Many2one('hr.recruitment.stage', string='Etapa de Verificacion', ondelete='cascade')
    
    @api.onchange("stage_id", "name")
    def _onchange_stage_id(self):
        if self.stage_id:
            self.name = _('Lista de Verificación para %s') % self.stage_id.name
        else:
            self.name = "/"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('stage_id') and not vals.get('name'):
                stage = self.env['hr.recruitment.stage'].browse(vals['stage_id'])
                vals['name'] = _('Lista de Verificación para %s') % stage.name
        return super().create(vals_list)

    def _create_lines_for_applicant(self, applicant):
        self.ensure_one()
        StageChecklistLine = self.env['hr.recruitment.stage.checklist.line']
        StageChecklistLine.create({
            'name': self.name,
            'stage_id': self.stage_id.id,
            'is_name': True,
            'applicant_id': applicant.id,
        })
        for line in self.line_ids:
            StageChecklistLine.create({
                'name': line.name,
                'stage_id': line.stage_id.id,
                'is_required': line.is_required,
                'applicant_id': applicant.id,
            })


class StageChecklistLine(models.Model):
    _name = 'hr.recruitment.stage.checklist.line'
    _description = 'Lineas de Verificación'

    name = fields.Char(string='Pregunta')
    checklist_id = fields.Many2one('hr.recruitment.stage.checklist', 'Lista de Verificación')
    stage_id = fields.Many2one('hr.recruitment.stage', string='Etapa de Verificacion', ondelete='cascade')
    # attachment_ids = fields.Many2many(
    #     comodel_name='ir.attachment',
    #     string='Documentacion',
    #     help="Adjunta documentos relacionados a esta verificacion."
    # )
    attachment_ids  = fields.Binary(string="Documentacion",attachment=True) 
    store_fname = fields.Char(string="File Name")
    is_required = fields.Boolean(string='Mandatorio', default=False)
    is_name = fields.Boolean(string='Es el Nombre', default=False)
    sequence = fields.Integer('Sequencia', related='stage_id.sequence')
    necessary = fields.Boolean(string="-")
    applicant_id = fields.Many2one('hr.applicant', string='Applicant', ondelete='cascade')

 
