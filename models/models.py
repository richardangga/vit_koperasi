# -*- coding: utf-8 -*-
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'
from odoo import models, fields, api, tools
from odoo.tools.translate import _
from odoo.exceptions import Warning
from dateutil.relativedelta import relativedelta as rd
import random
import datetime

STATES = [('draft','Draft'),('confirm','Pengajuan'),('validate', 'Disetujui'),('cair','Pencairan'),('lunas',"Lunas"),('macet',"Bermasalah")]

def rounding(arg1, arg2, arg3):
    if arg1 % arg2 > arg3:
        result = arg1 + (arg2 - arg1 % arg2)
    else:
        result = arg1 + (arg3 - arg1 % arg2)
    return result

class kredit(models.Model):
    _name = 'ksp.kredit'
    
    name = fields.Char('Name', default='Draft',states={'draft':[('readonly',True)]})
    kredit_type = fields.Many2one('ksp.kredit.type','Jenis Kredit',states={'draft':[('readonly',True)]})
    tanggal = fields.Date('Tanggal',states={'draft':[('readonly',True)]})
    tgl_cair = fields.Date('Tanggal Cair',states={'draft':[('readonly',True)]})
    account_cair = fields.Many2one('account.account','Metode Pencairan')
    partner_id = fields.Many2one('res.partner','Nasabah',states={'draft':[('readonly',True)]})
    pokok = fields.Integer('Pokok',default=0,states={'draft':[('readonly',True)]})
    bunga = fields.Integer('Bunga',default=0,compute='_hitung_bunga')
    tempo = fields.Integer('Jangka waktu', default=1,states={'draft':[('readonly',True)]})
    tempo_type = fields.Selection([('T','Tahun'),('B','Bulan')], default='B',states={'draft':[('readonly',True)]})
    angsuran = fields.Integer('Angsuran',compute='_hitung_angsuran')
    rate = fields.Float('Suku Bunga per bulan', default=0.0,states={'draft':[('readonly',True)]})
    rate_tempo = fields.Selection([('B','Bulan'),('T','Tahun')])
    rate_type = fields.Selection([
        ('F','Flat'),
        ('M','Flat Menurun'),
        ('A','Anuitet'),
        ('E','Efektif'),
        ('K','Kontrak')
    ], default='F',states={'draft':[('readonly',True)]})
    kredit_line = fields.One2many('ksp.kredit.line','kredit_id')
    biaya_line = fields.One2many('ksp.kredit.biaya.line','kredit_id')
    move_line = fields.One2many('account.move','kredit_id')
    jaminan_line = fields.One2many('ksp.kredit.jaminan.line','kredit_id')
    total_angsuran = fields.Integer('Total Angsuran', compute='_total_angsuran')
    total_pokok = fields.Integer('Total Pokok', compute='_total_angsuran')
    total_bunga = fields.Integer('Total Bunga', compute='_total_angsuran')
    sisa_angsuran = fields.Integer('Sisa Angsuran')
    sisa_pokok = fields.Integer('Sisa Pokok')
    sisa_bunga = fields.Integer('Sisa Bunga')
    bulat = fields.Boolean('Pembulatan', default=False,states={'draft':[('readonly',True)]})
    apply_1 = fields.Char('Apply 1')
    apply_2 = fields.Char('Apply 2')
    apply_to = fields.Datetime('apply timeout')
    apply_key = fields.Char('Key')
    state = fields.Selection(string="Status", selection=STATES, required=True, readonly=True, default=STATES[0][0])

    @api.one
    def _hitung_bunga(self):
        self.bunga = self.pokok*(self.rate/100)*self.tempo

    @api.one
    @api.depends('pokok','rate', 'rate_type', 'tempo')
    def _hitung_angsuran(self):
        if (self.rate_type=="F") or (self.rate_type=="M"):
            self.bunga = self.pokok*(self.rate/100)*self.tempo
            self.angsuran = (self.pokok +(self.pokok*(self.rate/100)*self.tempo))/ self.tempo
            if self.bulat == True:
                self.angsuran=rounding(self.angsuran,1000,500)
        elif (self.rate_type=="E"):
            angsur = self.tempo + 1
            tot_angsuran = 0
            self.angsuran = (self.pokok/self.tempo)+((self.pokok - ((1-1)*(self.pokok/self.tempo))) * (self.rate/100))
            for x in range(1,angsur):
                tot_angsuran += (self.pokok/self.tempo)+((self.pokok - ((x-1)*(self.pokok/self.tempo))) * (self.rate/100))
            self.bunga = tot_angsuran - self.pokok
        elif (self.rate_type=="A"):
            self.angsuran = self.pokok * ((self.rate/100)/(1-(1+(self.rate/100))**(self.tempo*-1)))
            tot_angsuran = self.angsuran * self.tempo
            self.bunga = tot_angsuran - self.pokok
        else:
            self.angsuran=99999

    @api.one
    @api.depends('apply_1')
    def generate_apply(self):
        self.apply_1 = str(int(random.random()*100000000))
        datenow = datetime.datetime.now() + rd(hours=-7) + rd(minutes=15)
        self.apply_to = datenow.strftime(DATETIME_FORMAT)
        key = datetime.datetime.now().strftime('%d%m%Y')
        key2 = sum(int(x) for x in key)
        key3 = ''
        for item in self.apply_1:
            key3 += str((int(item)*key2)%10)
        self.apply_key = key3
        return

    @api.one
    @api.depends('pokok','rate','rate_type','tempo','kredit_line')
    def generate_angsuran(self):
        angsur_total = angsur_bunga = angsur_pokok = 0
        angsur = self.tempo + 1
        tot_bunga = tot_pokok = 0
        krd_id = self.id
        self.env.cr.execute('DELETE FROM ksp_kredit_line WHERE kredit_id = %s' % krd_id)
        if self.rate_type == 'F':
            angsur_total = self.angsuran
            angsur_pokok = self.pokok / self.tempo
            angsur_bunga = angsur_total - angsur_pokok
            for x in range (1,angsur):
                self.kredit_line.create(
                    {
                        'kredit_id':self.id,
                        'sequence': x,
                        'angsuran': self.angsuran,
                        'pokok':angsur_pokok,
                        'bunga':angsur_bunga,
                        'sisa_pokok': angsur_pokok,
                        'sisa_bunga': angsur_bunga,
                        'sisa_angsuran': angsur_total,
                    }
                )
        elif self.rate_type == 'M':
            pembagi = 1.0/(sum(x for x in range(1,angsur)))
            angsuran = angsur_total = self.angsuran
            for x in range (1,angsur):
                if self.pokok > self.bunga:
                    angsur_bunga = (self.pokok*(self.rate/100)*self.tempo)*(pembagi*(angsur-x))
                    angsur_pokok = angsur_total - angsur_bunga
                else:
                    angsur_pokok = self.pokok*(pembagi*x)
                    angsur_bunga = angsur_total - angsur_pokok
                tot_bunga += angsur_bunga
                tot_pokok += angsur_pokok
                if x == (angsur - 1):
                    # self.name=str(tot_pokok)+'/' +str(self.pokok)
                    if tot_pokok > self.pokok :
                        angsur_pokok -= (tot_pokok - self.pokok)
                    elif tot_pokok < self.pokok :
                        angsur_pokok += (self.pokok - tot_pokok)
                    angsuran = angsur_pokok + angsur_bunga
                if x == (angsur - 1):
                    # self.name += ' '+str(tot_bunga)+'/'+str(self.bunga)
                    if tot_bunga > self.bunga:
                        angsur_bunga -= (tot_bunga - self.bunga)
                    elif tot_bunga < self.bunga:
                        angsur_bunga += (self.bunga - tot_bunga)
                    angsuran = angsur_pokok + angsur_bunga
                self.kredit_line.create(
                    {
                        'kredit_id': self.id,
                        'sequence': x,
                        'angsuran': angsuran,
                        'pokok':angsur_pokok,
                        'bunga':angsur_bunga,
                        'sisa_pokok': angsur_pokok,
                        'sisa_bunga': angsur_bunga,
                        'sisa_angsuran': angsur_total,
                    }
                )
        elif self.rate_type == "E":
            angsur_pokok = self.pokok/self.tempo
            for x in range(1,angsur):
                angsuran = (self.pokok/self.tempo)+((self.pokok - ((x-1)*(self.pokok/self.tempo))) * (self.rate/100))
                angsur_bunga = angsuran - angsur_pokok
                tot_bunga += angsur_bunga
                tot_pokok += angsur_pokok
                if x == (angsur - 1):
                    if tot_pokok > self.pokok :
                        angsur_pokok -= (tot_pokok - self.pokok)
                    elif tot_pokok < self.pokok :
                        angsur_pokok += (self.pokok - tot_pokok)
                    angsuran = angsur_pokok + angsur_bunga
                if x == (angsur - 1):
                    if tot_bunga > self.bunga:
                        angsur_bunga -= (tot_bunga - self.bunga)
                    elif tot_bunga < self.bunga:
                        angsur_bunga += (self.bunga - tot_bunga)
                    angsuran = angsur_pokok + angsur_bunga
                self.kredit_line.create(
                    {
                        'kredit_id': self.id,
                        'sequence': x,
                        'angsuran': angsuran,
                        'pokok': angsur_pokok,
                        'bunga': angsur_bunga,
                        'sisa_pokok': angsur_pokok,
                        'sisa_bunga': angsur_bunga,
                        'sisa_angsuran': angsur_total,
                    }
                )
        elif self.rate_type == 'A':
            angsuran = self.pokok * ((self.rate/100)/(1-(1+(self.rate/100))**(self.tempo*-1)))
            sisa_pokok = self.pokok
            denda = 0
            for x in range(1, angsur):
                angsur_bunga = sisa_pokok * (self.rate/100)
                angsur_pokok = angsuran - angsur_bunga
                tot_bunga += angsur_bunga
                tot_pokok += angsur_pokok
                sisa_pokok -= angsur_pokok
                if x == (angsur - 1):
                    if tot_pokok > self.pokok :
                        angsur_pokok -= (tot_pokok - self.pokok)
                        denda = 9999
                    elif tot_pokok < self.pokok :
                        denda = self.pokok - tot_pokok
                        angsur_pokok += (self.pokok - tot_pokok)
                    angsuran = angsur_pokok + angsur_bunga
                if x == (angsur - 1):
                    if tot_bunga > self.bunga:
                        angsur_bunga -= (tot_bunga - self.bunga)
                    elif tot_bunga < self.bunga:
                        angsur_bunga += (self.bunga - tot_bunga)
                    angsuran = angsur_pokok + angsur_bunga
                self.kredit_line.create(
                    {
                        'kredit_id': self.id,
                        'sequence': x,
                        'angsuran': angsuran,
                        'pokok': angsur_pokok,
                        'bunga': angsur_bunga,
                        'denda': denda,
                        'sisa_pokok': angsur_pokok,
                        'sisa_bunga': angsur_bunga,
                        'sisa_angsuran': angsur_total,
                    }
                )
        else:
            angsur_bunga = self.pokok * (self.rate/100) * self.tempo
            self.sisa_angsuran = self.sisa_pokok = self.sisa_bunga = 0
            for x in range (1,angsur):
                angsur_pokok = 0
                angsur_total = angsur_pokok + angsur_bunga
                if x == (angsur - 1):
                    angsur_pokok = self.pokok
                    angsur_total = angsur_pokok + angsur_bunga
                self.sisa_angsuran += angsur_total
                self.sisa_pokok += angsur_pokok
                self.sisa_bunga += angsur_bunga
                self.kredit_line.create(
                    {
                        'kredit_id':self.id,
                        'sequence': x,
                        'angsuran': angsur_total,
                        'pokok':angsur_pokok,
                        'bunga':angsur_bunga,
                        'sisa_pokok':angsur_pokok,
                        'sisa_bunga':angsur_bunga,
                        'sisa_angsuran':angsur_total,
                    }
                )
        self.env.cr.execute('DELETE FROM ksp_kredit_biaya_line WHERE kredit_id = %s' % krd_id)
        for x in self.kredit_type.kredit_line:
            nominal = ((x.rate/100)*self.pokok) + x.nominal
            self.name = str(self.pokok)+x.account_id.name
            self.biaya_line.create(
                {
                    'kredit_id': self.id,
                    'account_id': x.account_id.id,
                    'nominal': nominal
                }
            )
        return

    @api.one
    @api.depends('kredit_line.angsuran','kredit_line.pokok','kredit_line.bunga')
    def _total_angsuran(self):
        self.total_angsuran = self.total_bunga = self.total_pokok = 0
        self.sisa_angsuran = self.sisa_bunga = self.sisa_pokok = 0
        for line in self.kredit_line:
            self.total_angsuran += line.angsuran
            self.total_pokok += line.pokok
            self.total_bunga += line.bunga
            if line.lunas == False :
                self.sisa_angsuran += line.angsuran
                self.sisa_pokok += line.pokok
                self.sisa_bunga += line.bunga

    def confirm_kredit(self):
        self.state = 'confirm'
        self.name = self.env['ir.sequence'].next_by_code('ksp.kredit')
        for x in self.kredit_line:
            x.name = self.name+'/'+str(x.sequence).zfill(3)
        return

    def validasi_kredit(self):
        to = fields.Datetime.from_string(self.apply_to)
        sekarang = datetime.datetime.now() + rd(hours=-7)
        if (self.apply_2 == self.apply_key) and (to >= sekarang):
            self.state = 'validate'
        else:
            if to < sekarang:
                raise Warning(_('Tidak dapat divalidasi, token kadaluwarsa, silahkan generate token baru-2'))
            else:
                raise Warning(_('Tidak dapat divalidasi, kode apply 2 salah'))
        return

    def pencairan_kredit(self):
        pokok = self.pokok * 1.0
        total_biaya = sum(biaya.nominal for biaya in self.biaya_line)
        if self.account_cair.id == False:
            raise Warning(_('Metode Pencairan tidak boleh kosong'))
        else:
            self.state = 'cair'
            self.tgl_cair = fields.Date.today()
            tgl_cair = fields.Date.from_string(self.tgl_cair)
            for item in self.kredit_line:
                tgl_jt = tgl_cair + rd(months=item.sequence)
                item.tgl_jt = tgl_jt.strftime(DATE_FORMAT)
            move=self.env['account.move'].create(
                {
                    'date':self.tgl_cair,
                    'kredit_id':self.id ,
                    'partner_id':self.partner_id.id,
                    'journal_id':self.kredit_type.journal_cair.id,
                    'ref':self.name,
                }
            )
            self.env['account.move.line'].with_context(check_move_validity=False).create(
                {
                    'partner_id':self.partner_id.id,
                    'date':self.tgl_cair,
                    'journal_id':self.kredit_type.journal_cair.id,
                    'move_id': move.id,
                    'account_id': self.account_cair.id,
                    'credit': pokok-total_biaya,
                    'debit':0.0,
                    'name':self.name,
                }
            )
            for biaya in self.biaya_line:
                self.env['account.move.line'].with_context(check_move_validity=False).create(
                    {
                        'partner_id': self.partner_id.id,
                        'date': self.tgl_cair,
                        'journal_id': self.kredit_type.journal_cair.id,
                        'move_id': move.id,
                        'account_id': biaya.account_id.id,
                        'credit': biaya.nominal,
                        'debit': 0.0,
                        'name': self.name,
                    }
                )

            self.env['account.move.line'].create(
                {
                    'partner_id': self.partner_id.id,
                    'date': self.tgl_cair,
                    'journal_id': self.kredit_type.journal_cair.id,
                    'move_id': move.id,
                    'account_id': self.kredit_type.account_pokok.id,
                    'credit': 0.0,
                    'debit': pokok,
                    'name': self.name,
                }
            )
            move.post()
        return

    def pelunasan_kredit(self):
        self.state = 'lunas'
        return

    def kredit_macet(self):
        self.state = 'macet'
        return

    def button_cancel(self):
        if (self.state == 'lunas') or (self.state == 'macet') :
            self.state = 'cair'
        elif (self.state == 'cair'):
            self.state = 'validate'
        elif (self.state == 'validate'):
            self.state = 'confirm'
        else:
            self.state = 'draft'
        return


class kredit_line(models.Model):
    _name = 'ksp.kredit.line'
    _order = 'kredit_id, sequence'

    name = fields.Char('Name',default='Draft')
    sequence = fields.Integer('No. Urut',default=0)
    kredit_id = fields.Many2one('ksp.kredit')
    bayar_line = fields.One2many('ksp.kredit.line.bayar','kredit_line_id')
    tgl_jt = fields.Date('Tanggal Jatuh Tempo')
    tgl_bayar = fields.Date('Tanggal Lunas')
    angsuran = fields.Integer('Angsuran',default=0)
    pokok = fields.Integer('Pokok',default=0)
    bunga = fields.Integer('Bunga',default=0)
    denda = fields.Integer('Denda',compute='_hitung_denda')
    lunas = fields.Boolean('Lunas',default=0)
    sisa_pokok = fields.Integer('Sisa Pokok', compute='_hitung_bayar')
    sisa_bunga = fields.Integer('Sisa Bunga', compute='_hitung_bayar')
    sisa_angsuran = fields.Integer('Sisa Angsuran', compute='_hitung_bayar')
    pembayaran = fields.Integer('Total Pembayaran',compute='_hitung_bayar')
    is_denda = fields.Boolean('Tanpa Denda')

    @api.one
    def _hitung_denda(self):
        today = datetime.date.today()
        if self.tgl_jt != False:
            jtempo = fields.Date.from_string(self.tgl_jt)
            if jtempo < today :
                selisih = today - jtempo
                self.denda = self.kredit_id.kredit_type.denda * selisih.days
            else:
                self.denda = 0
        else:
            self.denda = 0

    def _hitung_bayar(self):
        self.pembayaran = sum(bayar.nominal for bayar in self.bayar_line )
        self.sisa_angsuran = self.angsuran - self.pembayaran
        if self.sisa_angsuran > 0:
            if self.pembayaran <= self.bunga:
                self.sisa_bunga = self.bunga - self.pembayaran
                self.sisa_pokok = self.pokok
            else:
                self.sisa_bunga = 0
                self.sisa_pokok = self.pokok - (self.pembayaran - self.bunga)
        else:
            self.lunas = True
        return

class kredit_jaminan_line(models.Model):
    _name = 'ksp.kredit.jaminan.line'

    name = fields.Char('name')
    kredit_id = fields.Many2one('ksp.kredit','Kredit Id')
    jaminan_id = fields.Many2one('ksp.jaminan','Jaminan id')
    nilai = fields.Integer('Nilai',compute='_get_nilai')

    @api.one
    @api.depends('jaminan_id')
    def _get_nilai(self):
        self.nilai = self.jaminan_id.harga_taksiran


class kredit_bayar(models.Model):
    _name = 'ksp.kredit.bayar'

    name = fields.Char('No. Kwitansi', default='Draft')
    kredit_id = fields.Many2one('ksp.kredit','no. kredit')
    account_id = fields.Many2one('account.account','Metode Pembayaran')
    date = fields.Date('Tanggal Bayar')
    bayar_line = fields.One2many('ksp.kredit.line.bayar', 'bayar_id')
    amount = fields.Integer('Nominal Pembayaran',default=0)
    total_paid = fields.Integer(compute='_hitung_bayar')
    user_id = fields.Many2one('res.users','operator')
    state = fields.Selection([
        ('draft','Draft'),
        ('confirm','Confirm'),
        ('post','Posting')
    ],default='draft')

    def _hitung_bayar(self):
        self.total_paid = sum(line.nominal for line in self.bayar_line)
        return

    def confirm_bayar(self):
        if self.total_paid != self.amount:
            raise Warning(_('Tidak dapat diconfirm, total pembayaran dan total detail tidak sama'))
        else:
            self.state = 'confirm'
        return

    def post_bayar(self):
        # total_posted = total_unposted = 0
        # for line in bayar_line:
        #     if line.state =
        self.state = 'post'
        return

    def cancel_bayar(self):
        if self.state == 'post':
            self.state = 'confirm'
        elif self.state == 'confirm':
            self.state = 'draft'
        return

class kredit_line_bayar(models.Model):
    _name = 'ksp.kredit.line.bayar'

    name = fields.Char()
    kredit_id = fields.Integer(compute='_get_kredit_id')
    kredit_line_id = fields.Many2one('ksp.kredit.line')
    bayar_id = fields.Many2one('ksp.kredit.bayar')
    angsur_id = fields.Many2one('ksp.kredit.line')
    tgl_bayar = fields.Date('Tanggal Bayar',related='bayar_id.date', store=True)
    nominal = fields.Integer('Nominal',default=0)
    user_id = fields.Many2one('res.users','operator')

    def _get_kredit_id(self):
        self.kredit_id = self.bayar_id.kredit_id.id
        return

class kredit_biaya_line(models.Model):
    _name = 'ksp.kredit.biaya.line'

    name = fields.Char()
    kredit_id = fields.Many2one('ksp.kredit')
    account_id = fields.Many2one('account.account')
    nominal = fields.Integer('Nominal',default=0)

class kredit_type(models.Model):
    _name = 'ksp.kredit.type'

    name = fields.Char()
    account_pokok = fields.Many2one('account.account','Akun Pokok')
    account_bunga = fields.Many2one('account.account','Akun Bunga')
    account_denda = fields.Many2one('account.account','Akun Denda')
    denda = fields.Integer('Nominal denda per hari')
    kredit_line = fields.One2many('ksp.kredit.type.line','kredit_id')
    seq_id = fields.Many2one('ir.sequence','Sequence Id')
    journal_cair = fields.Many2one('account.journal','Journal Pencairan')
    journal_angsur = fields.Many2one('account.journal','Journal Bayar Angsuran')

class kredit_type_line(models.Model):
    _name = 'ksp.kredit.type.line'

    name = fields.Char()
    kredit_id = fields.Many2one('ksp.kredit')
    account_id = fields.Many2one('account.account')
    rate = fields.Float('persentase -> pokok pinjaman', default=0.0)
    nominal = fields.Integer('Nominal',default=0)

class account_move(models.Model):
    _name = 'account.move'
    _inherit = 'account.move'

    kredit_id = fields.Many2one('ksp.kredit')

class res_partner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    kredit = fields.Boolean('Nasabah Kredit')
    deposito = fields.Boolean('Nasabah Deposito')
    tabungan = fields.Boolean('Nasabah Tabungan')
    no_id = fields.Char('N.I.K')

class ksp_jaminan(models.Model):
    _name = 'ksp.jaminan'

    name = fields.Char('Name')
    description = fields.Char('Deskripsi')
    image = fields.Binary("Image", attachment=True,
        help="This field holds the image used as avatar for this contact, limited to 1024x1024px",)
    image2 = fields.Binary("Image2", attachment=True,
        help="This field holds the image used as avatar for this contact, limited to 1024x1024px",)
    image3 = fields.Binary("Image3", attachment=True,
        help="This field holds the image used as avatar for this contact, limited to 1024x1024px",)
    image4 = fields.Binary("Image4", attachment=True,
        help="This field holds the image used as avatar for this contact, limited to 1024x1024px",)
    jenis = fields.Selection([
        ('mobil','Mobil'),
        ('motor',"Sepeda Motor"),
        ('sertifikat','Sertifikat'),
        ('other','Lain-lain'),
    ])
    merk = fields.Many2one("ksp.jaminan.merk","Merk")
    model = fields.Many2one("ksp.jaminan.model","Model")
    harga_pasar = fields.Integer("Harga Pasar",compute="_get_harga_pasar")
    harga_taksiran = fields.Integer("Harga Taksiran",help="Nilai jaminan sesuai dengan kondisi jaminan")
    type = fields.Char("Type",help="Diisi sesuai tipe di stnk")
    no_mesin = fields.Char("No. Mesin")
    no_rangka = fields.Char("No. Rangka")
    no_polisi = fields.Char("No. Polisi")
    no_bpkb = fields.Char("No. BPKB")
    tahun = fields.Char("Tahun")
    warna = fields.Char("Warna")
    nama_stnk = fields.Char("Atas nama STNK")
    alamat_stnk = fields.Char("Alamat STNK")
    no_sertifikat = fields.Char('Nomor Sertifikat')
    bentuk_sertifikat = fields.Char('Bentuk Sertifikat')
    alamat_sertifikat = fields.Char('Alamat')
    luas_sertifikat = fields.Char('Luas Tanah/Bangunan')
    no_surat_ukur = fields.Char('No. Surat Ukur')
    tgl_surat_ukur = fields.Char('Tanggal Surat Ukur')
    keterangan = fields.Text('Keterangan')

    @api.one
    @api.depends('model')
    def _get_harga_pasar(self):
        self.harga_pasar = self.model.harga_pasar

class ksp_jaminan_merk(models.Model):
    _name = "ksp.jaminan.merk"


    name = fields.Char('Nama')
    image = fields.Binary("Image", attachment=True, help="This field holds the image used as avatar for this contact, limited to 1024x1024px", )
    image_medium = fields.Binary("Medium Image", compute="_get_image", help="This field holds the image used as avatar for this contact, limited to 1024x1024px", )
    image_small = fields.Binary("Small Image", compute="_get_image", help="This field holds the image used as avatar for this contact, limited to 1024x1024px", )
    model_line = fields.One2many('ksp.jaminan.model','merk')
    jenis = fields.Selection([
        ('mobil','Mobil'),
        ('motor',"Sepeda Motor"),
        ('sertifikat','Sertifikat'),
        ('other','Lain-lain'),
    ])


    @api.one
    @api.depends("image")
    def _get_image(self):
        image = self.image
        data = tools.image_get_resized_images(image)
        self.image_medium = data["image_medium"]
        self.image_small = data["image_small"]


class ksp_jaminan_model(models.Model):
    _name = "ksp.jaminan.model"
    _order = "merk,name,tahun"

    name = fields.Char('Model')
    merk = fields.Many2one('ksp.jaminan.merk','Merk')
    tahun = fields.Char('Tahun')
    harga_pasar = fields.Integer('Harga Pasar')
    image = fields.Binary("Image", attachment=True,help="This field holds the image used as avatar for this contact, limited to 1024x1024px",)
    image_medium = fields.Binary("Medium Image", compute="_get_image", help="This field holds the image used as avatar for this contact, limited to 1024x1024px", )
    image_small = fields.Binary("Small Image", compute="_get_image", help="This field holds the image used as avatar for this contact, limited to 1024x1024px", )

    @api.one
    @api.depends("image")
    def _get_image(self):
        image = self.image
        data = tools.image_get_resized_images(image)
        self.image_medium = data["image_medium"]
        self.image_small = data["image_small"]
        return True
