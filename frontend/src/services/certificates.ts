import type { Cert, NewCert, Verification } from '../types';
import { EP } from './endpoints';
import { ApiError, http } from './http';
import { asList, mapCert, mapPublicRecord } from './mappers';

export const certificateService = {
  /** GET /certificates/ — a user gets their own, an admin gets everyone's (decided by the backend). */
  list: async (): Promise<Cert[]> => asList(await http<unknown>('GET', EP.certificates)).map(mapCert),

  /** GET /certificates/<id>/ */
  get: async (key: string): Promise<Cert> => mapCert(await http<unknown>('GET', EP.certificate(key))),

  /** POST /certificates/ (multipart) */
  async create(c: NewCert): Promise<Cert> {
    const f = new FormData();
    if (c.file) f.append('file', c.file);
    f.append('title', c.title);
    f.append('certificate_number', c.number);
    f.append('issuer', c.issuer);
    f.append('recipient_name', c.recipient);
    f.append('issue_date', c.issued);
    if (c.owner_id != null && c.owner_id !== '') {
      f.append('owner_id', String(c.owner_id));
      f.append('owner', String(c.owner_id));
    }
    return mapCert(await http<unknown>('POST', EP.certificates, f));
  },

  /** PATCH /certificates/<id>/ (admin only). Reassign owner or update fields. */
  async update(key: string, data: Partial<{ owner_id: number | string; title: string; recipient_name: string; issuer: string; issue_date: string }>): Promise<Cert> {
    return mapCert(await http<unknown>('PATCH', EP.certificate(key), data));
  },

  /** PATCH /certificates/<id>/review/ (admin only). A reason is required when rejecting. */
  async review(key: string, status: 'VERIFIED' | 'REJECTED', reason = ''): Promise<Cert> {
    return mapCert(await http<unknown>('PATCH', EP.review(key), { status, rejection_reason: reason }));
  },

  /** POST /certificates/<id>/retry-email/ (admin only). */
  async retryEmail(key: string | number): Promise<{ success: boolean; email_sent: boolean; message: string }> {
    return http<{ success: boolean; email_sent: boolean; message: string }>('POST', EP.retryEmail(key));
  },
};

export const courseService = {
  list: async (): Promise<import('../types').Course[]> =>
    asList(await http<unknown>('GET', EP.courses)) as unknown as import('../types').Course[],

  get: async (id: number | string): Promise<import('../types').Course> =>
    http<import('../types').Course>('GET', EP.course(id)),

  create: async (data: Omit<import('../types').Course, 'id'>): Promise<import('../types').Course> =>
    http<import('../types').Course>('POST', EP.courses, data),

  update: async (id: number | string, data: Partial<import('../types').Course>): Promise<import('../types').Course> =>
    http<import('../types').Course>('PATCH', EP.course(id), data),

  delete: async (id: number | string): Promise<void> =>
    http<void>('DELETE', EP.course(id)),
};

export const templateService = {
  list: async (): Promise<import('../types').CertificateTemplate[]> =>
    asList(await http<unknown>('GET', EP.templates)) as unknown as import('../types').CertificateTemplate[],

  get: async (id: number | string): Promise<import('../types').CertificateTemplate> =>
    http<import('../types').CertificateTemplate>('GET', EP.template(id)),

  upload: async (name: string, file: File): Promise<import('../types').CertificateTemplate> => {
    const f = new FormData();
    f.append('name', name);
    f.append('image', file);
    return http<import('../types').CertificateTemplate>('POST', EP.templates, f);
  },

  replace: async (id: number | string, file: File, name?: string): Promise<import('../types').CertificateTemplate> => {
    const f = new FormData();
    f.append('image', file);
    if (name) f.append('name', name);
    return http<import('../types').CertificateTemplate>('PUT', EP.template(id), f);
  },

  delete: async (id: number | string): Promise<void> =>
    http<void>('DELETE', EP.template(id)),
};

export const generationService = {
  /** Download CSV template blob / direct trigger */
  downloadCsvTemplateUrl: (): string => {
    const base = import.meta.env.VITE_API_BASE_URL || '/api';
    return `${base.replace(/\/$/, '')}${EP.csvTemplate}`;
  },

  /** Validate CSV file against selected course and student accounts.
   *  batchDefaults: optional batch-level overrides for course_name / dates,
   *  filled automatically from the selected course if not provided. */
  validateCsv: async (
    file: File,
    courseId?: number,
    batchDefaults?: {
      batch_course_name?: string;
      batch_start_date?: string;
      batch_end_date?: string;
      batch_issue_date?: string;
    }
  ): Promise<import('../types').CSVValidationResult> => {
    const f = new FormData();
    f.append('file', file);
    if (courseId) f.append('course_id', String(courseId));
    if (batchDefaults) {
      if (batchDefaults.batch_course_name) f.append('batch_course_name', batchDefaults.batch_course_name);
      if (batchDefaults.batch_start_date) f.append('batch_start_date', batchDefaults.batch_start_date);
      if (batchDefaults.batch_end_date) f.append('batch_end_date', batchDefaults.batch_end_date);
      if (batchDefaults.batch_issue_date) f.append('batch_issue_date', batchDefaults.batch_issue_date);
    }
    return http<import('../types').CSVValidationResult>('POST', EP.validateCsv, f);
  },

  /** Bulk generation from validated rows */
  bulkGenerate: async (
    courseId: number,
    templateId: number,
    rows: import('../types').CSVValidationRow[],
    sharedFields?: {
      course_name?: string;
      certificate_title?: string;
      issuer?: string;
      completion_description?: string;
      output_format?: string;
    }
  ): Promise<import('../types').GenerationBatch> => {
    return http<import('../types').GenerationBatch>('POST', EP.bulkGenerate, {
      course_id: courseId,
      template_id: templateId,
      rows,
      ...sharedFields,
    });
  },

  /** Single manual certificate generation */
  singleGenerate: async (payload: {
    course_id: number;
    template_id: number;
    user_id?: number | string;
    student_email?: string;
    student_name: string;
    course_name?: string;
    certificate_title?: string;
    issuer?: string;
    completion_description?: string;
    start_date: string;
    end_date: string;
    issue_date: string;
    output_format?: string;
    allow_reissue?: boolean;
  }): Promise<Cert> => {
    return mapCert(await http<unknown>('POST', EP.singleGenerate, payload));
  },

  /** Preview certificate image */
  preview: async (payload: {
    template_id: number;
    student_name?: string;
    course_name?: string;
    start_date?: string;
    end_date?: string;
    issue_date?: string;
    issuer_name?: string;
  }): Promise<{ preview_url: string; file_size: number; sha256: string }> => {
    return http<{ preview_url: string; file_size: number; sha256: string }>('POST', EP.previewCertificate, payload);
  },

  /** List generation batches */
  listBatches: async (): Promise<import('../types').GenerationBatch[]> =>
    asList(await http<unknown>('GET', EP.batches)) as unknown as import('../types').GenerationBatch[],

  /** Get generation batch detail */
  getBatch: async (id: number | string): Promise<import('../types').GenerationBatch> =>
    http<import('../types').GenerationBatch>('GET', EP.batch(id)),
};

export const verificationService = {
  /** GET /certificates/verify/<number>/ (public). 404 = no such certificate number. */
  async verify(raw: string): Promise<Verification> {
    const number = raw.trim().toUpperCase();
    try {
      const record = mapPublicRecord(await http<unknown>('GET', EP.verify(number), undefined, false));
      if (record.status === 'VERIFIED') return { kind: 'ok', title: 'Verified record', detail: `A record for ${number} exists and has been approved.`, record };
      if (record.status === 'REJECTED') return { kind: 'er', title: 'Record rejected', detail: `A record for ${number} exists but was rejected on review.`, record };
      return { kind: 'wn', title: 'Record found, pending review', detail: `A record for ${number} exists but has not been verified yet.`, record };
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        return { kind: 'wn', title: 'ID not found', detail: 'No matching record was found. This does not by itself mean the certificate is fake.' };
      }
      return { kind: 'er', title: 'Service error', detail: e instanceof Error ? e.message : 'The lookup service did not respond. This is not a negative result, please retry.' };
    }
  },
};
