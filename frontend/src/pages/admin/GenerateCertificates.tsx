import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FileStack,
  Upload,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Download,
  Eye,
  RefreshCw,
  Plus,
  ArrowRight,
  ArrowLeft,
  History,
  Sparkles,
  Pencil,
  Trash2,
  X,
} from 'lucide-react';
import {
  ApiError,
  courseService,
  templateService,
  generationService,
  errMsg,
} from '../../services';
import type {
  Course,
  CertificateTemplate,
  CSVValidationResult,
  CSVValidationRow,
  GenerationBatch,
} from '../../types';
import { localDateISO } from '../../lib/date';
import ErrorMessage from '../../components/ErrorMessage';
import LoadingSkeleton from '../../components/LoadingSkeleton';
import TemplateLayoutEditor from '../../components/TemplateLayoutEditor';
import { useAccessibleDialog } from '../../lib/dialog';

export default function GenerateCertificates() {
  // Stepper state: 1 = Course & Template, 2 = CSV & Validation, 3 = Preview & Confirm, 4 = Results
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);

  // Courses & Templates
  const [courses, setCourses] = useState<Course[]>([]);
  const [templates, setTemplates] = useState<CertificateTemplate[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<number | ''>('');
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | ''>('');
  const [loadingData, setLoadingData] = useState(true);

  // Batch-level defaults (editable before CSV validation)
  const [batchCourseName, setBatchCourseName] = useState('');
  const [batchCertificateTitle, setBatchCertificateTitle] = useState('');
  const [batchIssuer, setBatchIssuer] = useState('');
  const [batchStartDate, setBatchStartDate] = useState('');
  const [batchEndDate, setBatchEndDate] = useState('');
  const [batchIssueDate, setBatchIssueDate] = useState('');
  const [batchCompletionDescription, setBatchCompletionDescription] = useState('');
  const [deletingTemplate, setDeletingTemplate] = useState(false);

  // Editable rows (for per-row overrides in step 3)
  const [editableRows, setEditableRows] = useState<CSVValidationRow[]>([]);

  // Per-student inline row editing modal
  const [editingRowIndex, setEditingRowIndex] = useState<number | null>(null);
  const [editFormData, setEditFormData] = useState<CSVValidationRow | null>(null);
  const editRowDialogRef = useAccessibleDialog(Boolean(editFormData), () => setEditFormData(null));
  const [editNameError, setEditNameError] = useState<string | null>(null);

  const handleStartEditRow = (idx: number, row: CSVValidationRow) => {
    setEditingRowIndex(idx);
    setEditFormData({ ...row });
    setEditNameError(null);
  };

  const handleSaveEditRow = () => {
    if (editingRowIndex === null || !editFormData) return;
    const trimmedName = editFormData.student_name.trim();
    if (!trimmedName || trimmedName.length >= 30) {
      setEditNameError('Student name must be 1–29 characters.');
      return;
    }
    const normalizedEmail = editFormData.student_email.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      setEditNameError('Enter a valid student email address.');
      return;
    }
    const parseDateStr = (dStr: string) => {
      const parts = dStr.split('/');
      if (parts.length === 3) {
        return new Date(`${parts[2]}-${parts[1]}-${parts[0]}`);
      }
      return new Date(dStr);
    };
    if (editFormData.start_date && editFormData.end_date) {
      const dStart = parseDateStr(editFormData.start_date);
      const dEnd = parseDateStr(editFormData.end_date);
      if (!isNaN(dStart.getTime()) && !isNaN(dEnd.getTime()) && dEnd < dStart) {
        setEditNameError('End date cannot be earlier than start date.');
        return;
      }
    }
    const updated: CSVValidationRow = {
      ...editFormData,
      student_name: trimmedName,
      student_email: normalizedEmail,
    };
    setEditableRows((prev) =>
      prev.map((r, i) => (i === editingRowIndex ? updated : r))
    );
    setEditingRowIndex(null);
    setEditFormData(null);
    setEditNameError(null);
  };

  const handleCancelEditRow = () => {
    setEditingRowIndex(null);
    setEditFormData(null);
    setEditNameError(null);
  };

  // New Course modal / inline form state
  const [showNewCourse, setShowNewCourse] = useState(false);
  const [newCourseName, setNewCourseName] = useState('');
  const [newCourseTitle, setNewCourseTitle] = useState('Certificate of Completion');
  const [newCourseIssuer, setNewCourseIssuer] = useState('OneSmarter, Inc.');
  const [newCourseStart, setNewCourseStart] = useState('');
  const [newCourseEnd, setNewCourseEnd] = useState('');
  const [savingCourse, setSavingCourse] = useState(false);
  const [editingCourseId, setEditingCourseId] = useState<number | null>(null);
  const [deletingCourseId, setDeletingCourseId] = useState<number | null>(null);

  // Template upload state
  const [showUploadTemplate, setShowUploadTemplate] = useState(false);
  const [templateName, setTemplateName] = useState('OneSmarter Official Certificate');
  const [templateFile, setTemplateFile] = useState<File | null>(null);
  const [uploadingTemplate, setUploadingTemplate] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<CertificateTemplate | null>(null);

  // CSV file & validation
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [validatingCsv, setValidatingCsv] = useState(false);
  const [validationResult, setValidationResult] = useState<CSVValidationResult | null>(null);

  // Preview Certificate
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const previewDialogRef = useAccessibleDialog(Boolean(previewUrl), () => setPreviewUrl(null));
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Bulk Generation Execution
  const [generating, setGenerating] = useState(false);
  const [generationOutcomeUnknown, setGenerationOutcomeUnknown] = useState(false);
  const [batchResult, setBatchResult] = useState<GenerationBatch | null>(null);

  // Errors / alerts
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadInitialData = async () => {
    setLoadingData(true);
    setError(null);
    try {
      const [cList, tList] = await Promise.all([
        courseService.list(),
        templateService.list(),
      ]);
      setCourses(cList);
      setTemplates(tList);
      if (cList.length > 0 && selectedCourseId === '') {
        setSelectedCourseId(cList[0].id);
      }
      if (tList.length > 0 && selectedTemplateId === '') {
        setSelectedTemplateId(tList[0].id);
      }
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoadingData(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  const selectedCourse = courses.find((c) => c.id === Number(selectedCourseId));
  const selectedTemplate = templates.find((t) => t.id === Number(selectedTemplateId));

  // Handle New Course creation
  const handleCreateCourse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCourseName.trim()) {
      setError('Course name is required.');
      return;
    }
    if (!newCourseStart || !newCourseEnd) {
      setError('Start date and end date are required.');
      return;
    }
    if (newCourseEnd < newCourseStart) {
      setError('Course end date cannot be earlier than start date.');
      return;
    }

    if (newCourseStart && newCourseEnd && newCourseEnd < newCourseStart) {
      setError('End date cannot be earlier than start date.');
      return;
    }
    setSavingCourse(true);
    setError(null);
    try {
      const values = {
        name: newCourseName.trim(),
        title: newCourseTitle.trim() || 'Certificate of Completion',
        issuer: newCourseIssuer.trim() || 'OneSmarter, Inc.',
        start_date: newCourseStart,
        end_date: newCourseEnd,
      };
      const saved = editingCourseId
        ? await courseService.update(editingCourseId, values)
        : await courseService.create(values);
      setCourses((prev) => editingCourseId
        ? prev.map((course) => course.id === saved.id ? saved : course)
        : [saved, ...prev]);
      setSelectedCourseId(saved.id);
      setShowNewCourse(false);
      setEditingCourseId(null);
      setNewCourseName('');
      setNewCourseTitle('Certificate of Completion');
      setNewCourseIssuer('OneSmarter, Inc.');
      setNewCourseStart('');
      setNewCourseEnd('');
      setSuccessMsg(editingCourseId
        ? `Course "${saved.name}" updated successfully.`
        : `Course "${saved.name}" created successfully.`);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setSavingCourse(false);
    }
  };

  const handleEditCourse = (course: Course) => {
    setError(null);
    setSuccessMsg(null);
    setEditingCourseId(course.id);
    setNewCourseName(course.name);
    setNewCourseTitle(course.title);
    setNewCourseIssuer(course.issuer);
    setNewCourseStart(course.start_date);
    setNewCourseEnd(course.end_date);
    setShowNewCourse(true);
  };

  const handleDeleteCourse = async (course: Course) => {
    const confirmed = window.confirm(
      `Delete course "${course.name}"? This can affect related certificates and generation history. The server will block deletion if protected records are linked.`
    );
    if (!confirmed) return;
    setDeletingCourseId(course.id);
    setError(null);
    setSuccessMsg(null);
    try {
      await courseService.delete(course.id);
      setCourses((prev) => prev.filter((item) => item.id !== course.id));
      setSelectedCourseId((current) => current === course.id
        ? (courses.find((item) => item.id !== course.id)?.id ?? '')
        : current);
      setSuccessMsg(`Course "${course.name}" deleted successfully.`);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setDeletingCourseId(null);
    }
  };

  const toggleCourseForm = () => {
    if (showNewCourse) {
      setShowNewCourse(false);
      setEditingCourseId(null);
      setNewCourseName('');
      setNewCourseTitle('Certificate of Completion');
      setNewCourseIssuer('OneSmarter, Inc.');
      setNewCourseStart('');
      setNewCourseEnd('');
    } else {
      setEditingCourseId(null);
      setNewCourseName('');
      setNewCourseTitle('Certificate of Completion');
      setNewCourseIssuer('OneSmarter, Inc.');
      setNewCourseStart('');
      setNewCourseEnd('');
      setShowNewCourse(true);
    }
  };

  // Handle Template Upload
  const handleUploadTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!templateFile) {
      setError('Please select a PNG, JPEG, or PDF template file.');
      return;
    }
    setUploadingTemplate(true);
    setError(null);
    try {
      const uploaded = await templateService.upload(
        templateName.trim() || 'OneSmarter Certificate Template',
        templateFile
      );
      setTemplates((prev) => [uploaded, ...prev]);
      setSelectedTemplateId(uploaded.id);
      setShowUploadTemplate(false);
      setTemplateFile(null);
      setSuccessMsg(`Template "${uploaded.name}" uploaded successfully.`);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setUploadingTemplate(false);
    }
  };

  // Safe template deletion
  const handleDeleteTemplate = async (templateId: number) => {
    if (!window.confirm('Are you sure you want to delete this template? Unused templates can be deleted safely; templates linked to issued certificates are protected.')) {
      return;
    }
    setDeletingTemplate(true);
    setError(null);
    try {
      await templateService.delete(templateId);
      const remaining = templates.filter((t) => t.id !== templateId);
      setTemplates(remaining);
      if (selectedTemplateId === templateId) {
        setSelectedTemplateId(remaining.length > 0 ? remaining[0].id : '');
      }
      setSuccessMsg('Template deleted successfully.');
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setDeletingTemplate(false);
    }
  };

  // Handle CSV Validation
  const handleValidateCsv = async (fileToValidate?: File) => {
    const file = fileToValidate || csvFile;
    if (!file) {
      setError('Please select a CSV file to validate.');
      return;
    }
    setValidatingCsv(true);
    setError(null);
    try {
      const res = await generationService.validateCsv(
        file,
        selectedCourseId ? Number(selectedCourseId) : undefined,
        {
          batch_course_name: batchCourseName,
          batch_start_date: batchStartDate,
          batch_end_date: batchEndDate,
          batch_issue_date: batchIssueDate,
        }
      );
      setValidationResult(res);
      // Deep-copy rows so the user can edit them inline in step 3
      setEditableRows(res.rows.map((r) => ({ ...r })));
      setStep(3); // Advance to preview
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setValidatingCsv(false);
    }
  };

  // Handle Live Certificate Preview
  const handlePreviewCertificate = async (row?: CSVValidationRow) => {
    if (!selectedTemplateId) {
      setError('Please select a certificate template to preview.');
      return;
    }
    setLoadingPreview(true);
    try {
      const res = await generationService.preview({
        template_id: Number(selectedTemplateId),
        course_id: selectedCourse ? Number(selectedCourse.id) : undefined,
        student_name: row?.student_name || 'Kartik Hande',
        course_name: row?.course_name || selectedCourse?.name || '',
        start_date: row?.start_date || selectedCourse?.start_date || '',
        end_date: row?.end_date || selectedCourse?.end_date || '',
        issue_date: row?.issue_date || localDateISO(),
        issuer_name: selectedCourse?.issuer || 'OneSmarter, Inc.',
        completion_description: batchCompletionDescription.trim() || undefined,
      });
      setPreviewUrl(res.preview_url);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoadingPreview(false);
    }
  };

  // Handle Bulk Generation Execution
  const handleConfirmGeneration = async () => {
    if (!selectedCourseId || !selectedTemplateId || !validationResult) {
      setError('Missing course, template, or CSV validation result.');
      return;
    }

    const validRows = editableRows.filter((r) => r.is_valid);
    if (validRows.length === 0) {
      setError('There are no valid rows to generate certificates for.');
      return;
    }

    setGenerating(true);
    setGenerationOutcomeUnknown(false);
    setError(null);
    try {
      const result = await generationService.bulkGenerate(
        Number(selectedCourseId),
        Number(selectedTemplateId),
        validRows,
        {
          course_name: batchCourseName.trim() || undefined,
          certificate_title: batchCertificateTitle.trim() || undefined,
          issuer: batchIssuer.trim() || undefined,
          completion_description: batchCompletionDescription.trim() || undefined,
        }
      );
      setBatchResult(result);
      setStep(4); // Move to results step
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        setGenerationOutcomeUnknown(true);
        setError('The connection ended before the batch result was received. Check Generation History before starting another batch.');
      } else {
        setError(errMsg(err));
      }
    } finally {
      setGenerating(false);
    }
  };

  if (loadingData) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton lines={4} height="h-10" />
        <LoadingSkeleton lines={6} height="h-16" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-6 sm:p-8 text-white shadow-md border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight mt-2.5 flex items-center gap-3">
            <FileStack className="w-7 h-7 text-teal-400" />
            <span>Generate Certificates in Bulk</span>
          </h2>
          <p className="text-slate-300 text-sm mt-1 max-w-2xl">
            Generate authentic certificates in bulk, manage records, and automate email delivery with ease.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <a
            href={generationService.downloadCsvTemplateUrl()}
            download="certificate_upload_template.csv"
            className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-sm font-semibold transition inline-flex items-center gap-2 shadow-sm"
          >
            <Download className="w-4 h-4 text-teal-400" />
            <span>Download CSV Template</span>
          </a>
          <Link
            to="/admin/dashboard/generate-single"
            className="px-4 py-2.5 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-semibold shadow-sm transition inline-flex items-center gap-2"
          >
            <Sparkles className="w-4 h-4" />
            <span>Single Certificate</span>
          </Link>
          <Link
            to="/admin/dashboard/generation-history"
            className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-sm font-semibold transition inline-flex items-center gap-2"
          >
            <History className="w-4 h-4 text-indigo-400" />
            <span>History</span>
          </Link>
        </div>
      </div>

      {error && <ErrorMessage message={error} onRetry={() => setError(null)} />}
      {generationOutcomeUnknown && (
        <div role="status" className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
          A disconnected browser does not cancel server-side certificate generation. Review the batch status before retrying.
          <Link to="/admin/dashboard/generation-history" className="ml-2 font-semibold underline">Open Generation History</Link>
        </div>
      )}
      {successMsg && (
        <div className="p-4 rounded-xl bg-teal-50 dark:bg-teal-950/50 border border-teal-200 dark:border-teal-800 text-teal-800 dark:text-teal-200 text-xs font-medium flex items-center justify-between">
          <span>{successMsg}</span>
          <button
            onClick={() => setSuccessMsg(null)}
            className="text-teal-600 hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Stepper Indicator */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm">
        <div className="grid grid-cols-4 gap-2 text-center text-xs">
          <button
            type="button"
            onClick={() => setStep(1)}
            className={`p-2.5 rounded-xl font-semibold transition flex flex-col sm:flex-row items-center justify-center gap-2 ${step === 1
              ? 'bg-teal-50 text-teal-700 border border-teal-300 dark:bg-teal-950/60 dark:text-teal-300 dark:border-teal-700'
              : 'text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800'
              }`}
          >
            <span className="w-5 h-5 rounded-full bg-teal-600 text-white inline-flex items-center justify-center text-[10px]">
              1
            </span>
            <span>Course & Template</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (selectedCourseId && selectedTemplateId) setStep(2);
            }}
            disabled={!selectedCourseId || !selectedTemplateId}
            className={`p-2.5 rounded-xl font-semibold transition flex flex-col sm:flex-row items-center justify-center gap-2 ${step === 2
              ? 'bg-teal-50 text-teal-700 border border-teal-300 dark:bg-teal-950/60 dark:text-teal-300 dark:border-teal-700'
              : 'text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50'
              }`}
          >
            <span className="w-5 h-5 rounded-full bg-teal-600 text-white inline-flex items-center justify-center text-[10px]">
              2
            </span>
            <span>Upload CSV</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (validationResult) setStep(3);
            }}
            disabled={!validationResult}
            className={`p-2.5 rounded-xl font-semibold transition flex flex-col sm:flex-row items-center justify-center gap-2 ${step === 3
              ? 'bg-teal-50 text-teal-700 border border-teal-300 dark:bg-teal-950/60 dark:text-teal-300 dark:border-teal-700'
              : 'text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50'
              }`}
          >
            <span className="w-5 h-5 rounded-full bg-teal-600 text-white inline-flex items-center justify-center text-[10px]">
              3
            </span>
            <span>Preview & Validate</span>
          </button>

          <button
            type="button"
            disabled={!batchResult}
            className={`p-2.5 rounded-xl font-semibold transition flex flex-col sm:flex-row items-center justify-center gap-2 ${step === 4
              ? 'bg-teal-50 text-teal-700 border border-teal-300 dark:bg-teal-950/60 dark:text-teal-300 dark:border-teal-700'
              : 'text-slate-500 opacity-50'
              }`}
          >
            <span className="w-5 h-5 rounded-full bg-teal-600 text-white inline-flex items-center justify-center text-[10px]">
              4
            </span>
            <span>Batch Results</span>
          </button>
        </div>
      </div>

      {/* STEP 1: Select Course & Template */}
      {step === 1 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Course Selection Card */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Step 1A: Select Course
                </h3>
              </div>
              <button
                type="button"
                onClick={toggleCourseForm}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400 rounded-xl text-xs font-semibold hover:bg-teal-100 dark:hover:bg-teal-900 transition border border-teal-200 dark:border-teal-800"
              >
                {showNewCourse ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
                <span>{showNewCourse ? 'Close' : 'New Course'}</span>
              </button>
            </div>

            {showNewCourse ? (
              <form onSubmit={handleCreateCourse} className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700 space-y-3 text-xs">
                <h4 className="font-semibold text-slate-900 dark:text-white">{editingCourseId ? 'Edit Course' : 'Register New Course'}</h4>
                <div>
                  <label htmlFor="new-course-name" className="block text-slate-600 dark:text-slate-300 mb-1">Course Name *</label>
                  <input
                    id="new-course-name"
                    type="text"
                    required
                    placeholder="e.g. Python Programming Masterclass"
                    value={newCourseName}
                    onChange={(e) => setNewCourseName(e.target.value)}
                    className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="new-course-title" className="block text-slate-600 dark:text-slate-300 mb-1">Certificate Title</label>
                    <input
                      id="new-course-title"
                      type="text"
                      value={newCourseTitle}
                      onChange={(e) => setNewCourseTitle(e.target.value)}
                      className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                    />
                  </div>
                  <div>
                    <label htmlFor="new-course-issuer" className="block text-slate-600 dark:text-slate-300 mb-1">Issuing Authority</label>
                    <input
                      id="new-course-issuer"
                      type="text"
                      value={newCourseIssuer}
                      onChange={(e) => setNewCourseIssuer(e.target.value)}
                      className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="new-course-start" className="block text-slate-600 dark:text-slate-300 mb-1">Start Date *</label>
                    <input
                      id="new-course-start"
                      type="date"
                      required
                      value={newCourseStart}
                      onChange={(e) => setNewCourseStart(e.target.value)}
                      className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                    />
                  </div>
                  <div>
                    <label htmlFor="new-course-end" className="block text-slate-600 dark:text-slate-300 mb-1">End Date *</label>
                    <input
                      id="new-course-end"
                      type="date"
                      required
                      min={newCourseStart || undefined}
                      value={newCourseEnd}
                      onChange={(e) => setNewCourseEnd(e.target.value)}
                      className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={toggleCourseForm}
                    className="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-200 dark:text-slate-400"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={savingCourse}
                    className="px-3.5 py-1.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold rounded-lg shadow-sm"
                  >
                    {savingCourse ? 'Saving...' : editingCourseId ? 'Save Changes' : 'Save Course'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-3">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Select from Registered Courses:
                </label>
                <select
                  value={selectedCourseId}
                  onChange={(e) => setSelectedCourseId(Number(e.target.value))}
                  className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500"
                >
                  {courses.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.start_date} to {c.end_date}) — {c.issuer}
                    </option>
                  ))}
                </select>

                {selectedCourse && (
                  <div className="p-4 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700 text-xs space-y-1.5">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Certificate Title:</span>
                      <span className="font-semibold text-slate-900 dark:text-white">{selectedCourse.title}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Issuer:</span>
                      <span className="font-semibold text-slate-900 dark:text-white">{selectedCourse.issuer}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Duration:</span>
                      <span className="font-semibold text-slate-900 dark:text-white">
                        {selectedCourse.start_date} → {selectedCourse.end_date}
                      </span>
                    </div>
                    <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200 pt-3 mt-3 dark:border-slate-700">
                      <button
                        type="button"
                        onClick={() => handleEditCourse(selectedCourse)}
                        disabled={savingCourse || deletingCourseId !== null}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 font-semibold text-slate-700 hover:bg-white disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
                      >
                        <Pencil className="h-3.5 w-3.5" /> Edit course
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteCourse(selectedCourse)}
                        disabled={savingCourse || deletingCourseId !== null}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 px-3 py-1.5 font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900 dark:text-rose-300 dark:hover:bg-rose-950/50"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        {deletingCourseId === selectedCourse.id ? 'Deleting…' : 'Delete course'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Template Selection Card */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Step 1B: Certificate Template
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowUploadTemplate(!showUploadTemplate)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400 rounded-xl text-xs font-semibold hover:bg-teal-100 dark:hover:bg-teal-900 transition border border-teal-200 dark:border-teal-800"
              >
                <Upload className="w-3.5 h-3.5" />
                <span>{showUploadTemplate ? 'Close' : 'Upload Template'}</span>
              </button>
            </div>

            {showUploadTemplate ? (
              <form onSubmit={handleUploadTemplate} className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700 space-y-3 text-xs">
                <h4 className="font-semibold text-slate-900 dark:text-white">Upload Certificate Image Template</h4>
                <div>
                  <label htmlFor="upload-template-name" className="block text-slate-600 dark:text-slate-300 mb-1">Template Name *</label>
                  <input
                    id="upload-template-name"
                    type="text"
                    required
                    value={templateName}
                    onChange={(e) => setTemplateName(e.target.value)}
                    className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                  />
                </div>
                <div>
                  <label htmlFor="upload-template-file" className="block text-slate-600 dark:text-slate-300 mb-1">Select PNG, JPG, or PDF Template File *</label>
                  <input
                    id="upload-template-file"
                    type="file"
                    required
                    accept=".png,.jpg,.jpeg,.pdf"
                    onChange={(e) => setTemplateFile(e.target.files?.[0] || null)}
                    className="w-full text-xs text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-teal-600 file:text-white hover:file:bg-teal-700"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">
                    Accepts PNG, JPEG, and PDF documents. PDF templates are rendered with high-fidelity typography preservation.
                  </p>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowUploadTemplate(false)}
                    className="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-200 dark:text-slate-400"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={uploadingTemplate}
                    className="px-3.5 py-1.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold rounded-lg shadow-sm"
                  >
                    {uploadingTemplate ? 'Uploading...' : 'Upload Template'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-3">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Select Template:
                </label>
                {templates.length === 0 ? (
                  <p className="text-xs text-amber-600 dark:text-amber-400 py-3">
                    No certificate template uploaded yet. Please click &quot;Upload Template&quot; above to upload the OneSmarter background template.
                  </p>
                ) : (
                  <select
                    value={selectedTemplateId}
                    onChange={(e) => setSelectedTemplateId(Number(e.target.value))}
                    className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500"
                  >
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} ({t.file_format || 'PNG'} v{t.version || 1})
                      </option>
                    ))}
                  </select>
                )}

                {selectedTemplate && selectedTemplate.image_url && (
                  <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200 dark:border-slate-700 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <img
                        src={selectedTemplate.image_url}
                        alt={selectedTemplate.name}
                        className="w-20 h-14 object-cover rounded-lg border border-slate-300 shadow-sm"
                      />
                      <div className="text-xs">
                        <div className="flex items-center gap-2">
                          <p className="font-semibold text-slate-900 dark:text-white">{selectedTemplate.name}</p>
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-teal-100 dark:bg-teal-900/60 text-teal-800 dark:text-teal-300">
                            {selectedTemplate.file_format || 'PNG'}
                          </span>
                          <span className="text-[10px] text-slate-400">
                            v{selectedTemplate.version || 1}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => handlePreviewCertificate()}
                          className="mt-1 text-teal-600 hover:underline flex items-center gap-1"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>Test Preview</span>
                        </button>
                        <button type="button" onClick={() => setEditingTemplate(selectedTemplate)} className="mt-1 ml-3 text-blue-600 hover:underline inline-flex items-center gap-1">
                          <Pencil className="w-3.5 h-3.5" /><span>Edit template layout</span>
                        </button>
                      </div>
                    </div>
                    <button
                      type="button"
                      disabled={deletingTemplate}
                      onClick={() => handleDeleteTemplate(selectedTemplate.id)}
                      className="px-2.5 py-1.5 text-[11px] font-semibold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg transition border border-rose-200 dark:border-rose-900/50"
                      title="Delete unused template safely"
                    >
                      {deletingTemplate ? 'Deleting...' : 'Delete'}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="lg:col-span-2 flex justify-end">
            <button
              type="button"
              disabled={!selectedCourseId || !selectedTemplateId}
              onClick={() => setStep(2)}
              className="px-6 py-3 bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-white font-semibold rounded-xl text-sm shadow-sm inline-flex items-center gap-2 transition"
            >
              <span>Next: Upload CSV</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: CSV Upload & Validation */}
      {step === 2 && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white">
              Step 2: Upload Student Roster CSV
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Target Course: <strong className="text-slate-800 dark:text-slate-200">{selectedCourse?.name}</strong> | Template: <strong className="text-slate-800 dark:text-slate-200">{selectedTemplate?.name}</strong>
            </p>
          </div>

          {/* Batch Common Certificate Fields Card */}
          <div className="p-5 bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 rounded-xl space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                  Batch Certificate Fields Configuration
                </h4>
              </div>
              <span className="px-2.5 py-1 bg-teal-100 text-teal-800 dark:bg-teal-900/60 dark:text-teal-300 rounded-full text-[11px] font-semibold">
                Batch Defaults
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-x-4 gap-y-3 text-xs">
              <div>
                <label className="block min-h-8 text-slate-600 dark:text-slate-300 mb-1 font-medium">
                  Course Name Override (optional)
                </label>
                <input
                  type="text"
                  value={batchCourseName}
                  onChange={(e) => setBatchCourseName(e.target.value)}
                  className="w-full max-w-md px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white font-medium"
                />
              </div>

              <div>
                <label className="block min-h-8 text-slate-600 dark:text-slate-300 mb-1 font-medium">
                  Certificate Title (optional)
                </label>
                <input
                  type="text"
                  value={batchCertificateTitle}
                  onChange={(e) => setBatchCertificateTitle(e.target.value)}
                  className="w-full max-w-sm px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block min-h-8 text-slate-600 dark:text-slate-300 mb-1 font-medium">
                  Issuing Authority (optional)
                </label>
                <input
                  type="text"
                  value={batchIssuer}
                  onChange={(e) => setBatchIssuer(e.target.value)}
                  className="w-full max-w-sm px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block min-h-8 text-slate-600 dark:text-slate-300 mb-1 font-medium">
                  Start Date Override (optional)
                </label>
                <input
                  type="date"
                  value={batchStartDate}
                  onChange={(e) => setBatchStartDate(e.target.value)}
                  className="w-full max-w-[16rem] px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block min-h-8 text-slate-600 dark:text-slate-300 mb-1 font-medium">
                  End Date Override (optional)
                </label>
                <input
                  type="date"
                  min={batchStartDate || undefined}
                  value={batchEndDate}
                  onChange={(e) => setBatchEndDate(e.target.value)}
                  className={`w-full max-w-[16rem] px-3 py-2 bg-white dark:bg-slate-900 border rounded-lg text-slate-900 dark:text-white ${batchStartDate && batchEndDate && batchEndDate < batchStartDate
                    ? 'border-rose-400 focus:ring-rose-500'
                    : 'border-slate-300 dark:border-slate-700'
                    }`}
                />
              </div>

              <div>
                <label className="block min-h-8 text-slate-600 dark:text-slate-300 mb-1 font-medium">
                  Issue Date Override (optional)
                </label>
                <input
                  type="date"
                  value={batchIssueDate}
                  onChange={(e) => setBatchIssueDate(e.target.value)}
                  className="w-full max-w-[16rem] px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block min-h-8 text-slate-600 dark:text-slate-300 mb-1 font-medium">
                  Completion Description (optional)
                </label>
                <input
                  type="text"
                  value={batchCompletionDescription}
                  onChange={(e) => setBatchCompletionDescription(e.target.value)}
                  className="w-full max-w-md px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                />
              </div>
            </div>
            {batchStartDate && batchEndDate && batchEndDate < batchStartDate && (
              <p className="text-xs text-rose-500 font-medium">
                End date cannot be earlier than start date.
              </p>
            )}
          </div>

          {/* Download sample CSV hint */}
          <div className="p-4 bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 rounded-xl text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-teal-900 dark:text-teal-200">
                Simplified Two-Column CSV Format:
              </p>
              <code className="block mt-1 font-mono text-[11px] text-teal-800 dark:text-teal-300">
                student_name,student_email
              </code>
            </div>
            <a
              href={generationService.downloadCsvTemplateUrl()}
              download="certificate_upload_template.csv"
              className="px-3.5 py-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold rounded-xl shadow-sm inline-flex items-center gap-1.5 flex-shrink-0"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download CSV Template</span>
            </a>
          </div>

          {/* File input / drop zone */}
          <div className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-2xl p-8 text-center space-y-3">
            <Upload className="w-10 h-10 text-slate-400 mx-auto" />
            <div>
              <label className="cursor-pointer inline-flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-xl text-xs font-semibold transition">
                <span>Browse CSV File</span>
                <input
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0] || null;
                    setCsvFile(f);
                    if (f) handleValidateCsv(f);
                  }}
                />
              </label>
            </div>
            {csvFile ? (
              <p className="text-xs font-medium text-teal-600 dark:text-teal-400">
                Selected file: {csvFile.name} ({(csvFile.size / 1024).toFixed(1)} KB)
              </p>
            ) : (
              <p className="text-xs text-slate-400">
                Supports UTF-8 CSV files with up to 1,000 students per batch
              </p>
            )}
          </div>

          <div className="flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-semibold rounded-xl text-xs inline-flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back</span>
            </button>
            <button
              type="button"
              disabled={!csvFile || validatingCsv}
              onClick={() => handleValidateCsv()}
              className="px-6 py-2.5 bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-white font-semibold rounded-xl text-xs inline-flex items-center gap-2 shadow-sm transition"
            >
              {validatingCsv ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Validating CSV & Registered Accounts...</span>
                </>
              ) : (
                <>
                  <span>Validate CSV & Preview</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: Preview & Confirm */}
      {step === 3 && validationResult && (
        <div className="space-y-6">
          {/* Summary metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm text-xs">
              <span className="text-slate-500 block">Total Roster Rows</span>
              <span className="text-2xl font-bold text-slate-900 dark:text-white mt-1 block">
                {editableRows.length}
              </span>
            </div>
            <div className="p-4 bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 rounded-2xl shadow-sm text-xs">
              <span className="text-teal-700 dark:text-teal-400 block">Ready for Generation</span>
              <span className="text-2xl font-bold text-teal-800 dark:text-teal-200 mt-1 block flex items-center gap-2">
                <CheckCircle2 className="w-6 h-6 text-teal-600" />
                <span>{editableRows.filter((r) => r.is_valid).length} Valid</span>
              </span>
            </div>
            <div className="p-4 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded-2xl shadow-sm text-xs">
              <span className="text-rose-700 dark:text-rose-400 block">Invalid / Blocked Rows</span>
              <span className="text-2xl font-bold text-rose-800 dark:text-rose-200 mt-1 block flex items-center gap-2">
                <XCircle className="w-6 h-6 text-rose-600" />
                <span>{editableRows.filter((r) => !r.is_valid).length} Errors</span>
              </span>
            </div>
          </div>

          {/* Student rows table */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Validated Student Roster
                </h3>
              </div>
              <button
                type="button"
                disabled={loadingPreview}
                onClick={() => handlePreviewCertificate()}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-xl text-xs font-semibold inline-flex items-center gap-1.5 disabled:opacity-50"
              >
                {loadingPreview ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-teal-600" />
                ) : (
                  <Eye className="w-3.5 h-3.5 text-teal-600" />
                )}
                <span>{loadingPreview ? 'Rendering...' : 'Render Sample Preview'}</span>
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="py-3 px-4">Row #</th>
                    <th className="py-3 px-4">Student Name</th>
                    <th className="py-3 px-4">Registered Email</th>
                    <th className="py-3 px-4">Course</th>
                    <th className="py-3 px-4">Dates</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Validation Notes</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {editableRows.map((r, idx) => (
                    <tr
                      key={r.row_number}
                      className={
                        r.is_valid
                          ? 'hover:bg-slate-50/60 dark:hover:bg-slate-800/30'
                          : 'bg-rose-50/40 dark:bg-rose-950/20'
                      }
                    >
                      <td className="py-3 px-4 font-mono text-slate-500">#{r.row_number}</td>
                      <td className="py-3 px-4 font-semibold text-slate-900 dark:text-white">
                        {r.student_name}
                      </td>
                      <td className="py-3 px-4 text-slate-600 dark:text-slate-300 font-mono text-[11px]">
                        {r.student_email}
                      </td>
                      <td className="py-3 px-4 text-slate-600 dark:text-slate-400">
                        {r.course_name}
                      </td>
                      <td className="py-3 px-4 text-slate-500 whitespace-nowrap text-[11px]">
                        {r.start_date} → {r.end_date}
                      </td>
                      <td className="py-3 px-4">
                        {r.is_valid ? (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-teal-100 text-teal-800 dark:bg-teal-900/60 dark:text-teal-300 inline-flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Valid</span>
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-300 inline-flex items-center gap-1">
                            <XCircle className="w-3 h-3" />
                            <span>Error</span>
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-xs">
                        {r.errors.length > 0 ? (
                          <ul className="text-rose-600 dark:text-rose-400 list-disc list-inside space-y-0.5 text-[11px]">
                            {r.errors.map((err, i) => (
                              <li key={i}>{err}</li>
                            ))}
                          </ul>
                        ) : (
                          <span className="text-teal-600 dark:text-teal-400 text-[11px]">
                            Eligible for issuance. Recipient ownership will be resolved during generation.
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right whitespace-nowrap">
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            type="button"
                            aria-label={`Edit certificate fields for ${r.student_name}`}
                            onClick={() => handleStartEditRow(idx, r)}
                            className="p-1.5 text-slate-600 hover:text-teal-600 bg-slate-100 hover:bg-teal-50 dark:bg-slate-800 dark:hover:bg-teal-950/60 rounded-lg transition"
                            title="Edit certificate fields for this student"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            aria-label={`Preview certificate for ${r.student_name}`}
                            onClick={() => handlePreviewCertificate(r)}
                            className="p-1.5 text-teal-600 hover:text-teal-700 bg-teal-50 dark:bg-teal-950/60 rounded-lg transition"
                            title="Preview personalized certificate"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={() => setStep(2)}
              className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-semibold rounded-xl text-xs inline-flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to CSV Upload</span>
            </button>
            <button
              type="button"
              disabled={generating || generationOutcomeUnknown || editableRows.filter((r) => r.is_valid).length === 0}
              onClick={handleConfirmGeneration}
              className="px-6 py-2.5 bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-white font-semibold rounded-xl text-xs inline-flex items-center gap-2 shadow-sm transition"
            >
              {generating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Generating {editableRows.filter((r) => r.is_valid).length} Certificates...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Confirm & Generate {editableRows.filter((r) => r.is_valid).length} Certificates</span>
                </>
              )}
            </button>
          </div>

          {/* Row Edit Modal */}
          {editingRowIndex !== null && editFormData && (
            <div ref={editRowDialogRef} role="dialog" aria-modal="true" aria-label={`Edit certificate fields for row ${editFormData.row_number}`} tabIndex={-1} className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                  <h4 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <Pencil className="w-4 h-4 text-teal-600" />
                    <span>Edit Certificate Fields for Row #{editFormData.row_number}</span>
                  </h4>
                  <button
                    type="button"
                    onClick={handleCancelEditRow}
                    className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="space-y-3 text-xs">
                  <div>
                    <label htmlFor="edit-roster-recipient-name" className="block text-slate-600 dark:text-slate-300 mb-1 font-medium">
                      Recipient Name (1–29 chars) *
                    </label>
                    <input
                      id="edit-roster-recipient-name"
                      type="text"
                      maxLength={29}
                      value={editFormData.student_name}
                      onChange={(e) => {
                        const val = e.target.value;
                        setEditFormData({ ...editFormData, student_name: val });
                        if (val.trim().length >= 30) {
                          setEditNameError('Student name must be 1–29 characters.');
                        } else {
                          setEditNameError(null);
                        }
                      }}
                      className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                    />
                    {editNameError && (
                      <p className="text-rose-500 text-[11px] mt-1">{editNameError}</p>
                    )}
                  </div>

                  <div>
                    <label htmlFor="edit-roster-recipient-email" className="block text-slate-600 dark:text-slate-300 mb-1 font-medium">
                      Recipient Email *
                    </label>
                    <input
                      id="edit-roster-recipient-email"
                      type="email"
                      value={editFormData.student_email}
                      onChange={(e) =>
                        setEditFormData({ ...editFormData, student_email: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white font-mono"
                    />
                  </div>

                  <div>
                    <label htmlFor="edit-roster-course-name" className="block text-slate-600 dark:text-slate-300 mb-1 font-medium">
                      Course Name Override
                    </label>
                    <input
                      id="edit-roster-course-name"
                      type="text"
                      value={editFormData.course_name}
                      onChange={(e) =>
                        setEditFormData({ ...editFormData, course_name: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label htmlFor="edit-roster-start-date" className="block text-slate-600 dark:text-slate-300 mb-1 font-medium">
                        Start Date (DD/MM/YYYY)
                      </label>
                      <input
                        id="edit-roster-start-date"
                        type="text"
                        placeholder="DD/MM/YYYY"
                        value={editFormData.start_date}
                        onChange={(e) =>
                          setEditFormData({ ...editFormData, start_date: e.target.value })
                        }
                        className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                      />
                    </div>
                    <div>
                      <label htmlFor="edit-roster-end-date" className="block text-slate-600 dark:text-slate-300 mb-1 font-medium">
                        End Date (DD/MM/YYYY)
                      </label>
                      <input
                        id="edit-roster-end-date"
                        type="text"
                        placeholder="DD/MM/YYYY"
                        value={editFormData.end_date}
                        onChange={(e) =>
                          setEditFormData({ ...editFormData, end_date: e.target.value })
                        }
                        className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                      />
                    </div>
                  </div>

                  <div>
                    <label htmlFor="edit-roster-issue-date" className="block text-slate-600 dark:text-slate-300 mb-1 font-medium">
                      Issue Date (DD/MM/YYYY)
                    </label>
                    <input
                      id="edit-roster-issue-date"
                      type="text"
                      placeholder="DD/MM/YYYY"
                      value={editFormData.issue_date}
                      onChange={(e) =>
                        setEditFormData({ ...editFormData, issue_date: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-800">
                  <button
                    type="button"
                    onClick={() => handlePreviewCertificate(editFormData)}
                    className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold inline-flex items-center gap-1.5"
                  >
                    <Eye className="w-3.5 h-3.5 text-teal-600" />
                    <span>Preview This Student</span>
                  </button>

                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={handleCancelEditRow}
                      className="px-3.5 py-1.5 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-xs font-medium"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleSaveEditRow}
                      className="px-4 py-1.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold rounded-lg text-xs shadow-sm"
                    >
                      Save Changes
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* STEP 4: Results */}
      {step === 4 && batchResult && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-teal-50 dark:bg-teal-950/60 rounded-2xl text-teal-600 border border-teal-200 dark:border-teal-800">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                    Bulk Generation Job #{batchResult.id} Finished
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Course: <strong>{batchResult.course_name}</strong> | Status: <strong>{batchResult.status}</strong>
                  </p>
                </div>
              </div>
              <Link
                to="/admin/dashboard/certificates"
                className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold rounded-xl shadow-sm inline-flex items-center gap-1.5"
              >
                <span>View Manage Certificates</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {/* Results Counters */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
              <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-xl text-xs">
                <span className="text-slate-500 block">Total Rows</span>
                <span className="text-xl font-bold text-slate-900 dark:text-white mt-0.5 block">
                  {batchResult.total_rows}
                </span>
              </div>
              <div className="p-3 bg-teal-50 dark:bg-teal-950/60 rounded-xl text-xs">
                <span className="text-teal-700 dark:text-teal-300 block">Generated</span>
                <span className="text-xl font-bold text-teal-700 dark:text-teal-300 mt-0.5 block">
                  {batchResult.successful}
                </span>
              </div>
              <div className="p-3 bg-amber-50 dark:bg-amber-950/60 rounded-xl text-xs">
                <span className="text-amber-700 dark:text-amber-300 block">Skipped Dupes</span>
                <span className="text-xl font-bold text-amber-700 dark:text-amber-300 mt-0.5 block">
                  {batchResult.skipped_duplicates}
                </span>
              </div>
              <div className="p-3 bg-rose-50 dark:bg-rose-950/60 rounded-xl text-xs">
                <span className="text-rose-700 dark:text-rose-300 block">Failed Rows</span>
                <span className="text-xl font-bold text-rose-700 dark:text-rose-300 mt-0.5 block">
                  {batchResult.failed}
                </span>
              </div>
              <div className="p-3 bg-indigo-50 dark:bg-indigo-950/60 rounded-xl text-xs">
                <span className="text-indigo-700 dark:text-indigo-300 block">Emails Dispatched</span>
                <span className="text-xl font-bold text-indigo-700 dark:text-indigo-300 mt-0.5 block">
                  {batchResult.emails_sent}
                </span>
              </div>
              <div className="p-3 bg-slate-100 dark:bg-slate-800 rounded-xl text-xs">
                <span className="text-slate-600 dark:text-slate-400 block">Email Pending</span>
                <span className="text-xl font-bold text-slate-700 dark:text-slate-300 mt-0.5 block">
                  {batchResult.emails_failed}
                </span>
              </div>
            </div>

            {/* Error Report if any */}
            {batchResult.error_report && batchResult.error_report.length > 0 && (
              <div className="p-4 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 rounded-xl space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-rose-900 dark:text-rose-300 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-rose-600" />
                    <span>Failed or Skipped Entries ({batchResult.error_report.length})</span>
                  </h4>
                </div>
                <div className="max-h-60 overflow-y-auto divide-y divide-rose-200 dark:divide-rose-900">
                  {batchResult.error_report.map((item, idx) => (
                    <div key={idx} className="py-2 flex items-center justify-between gap-4 text-[11px]">
                      <div>
                        <span className="font-mono font-semibold">Row #{item.row_number}: </span>
                        <span>{item.student_name} ({item.student_email})</span>
                      </div>
                      <span className="text-rose-600 font-medium">{item.error}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-2">
              <button
                type="button"
                onClick={() => {
                  setStep(1);
                  setValidationResult(null);
                  setBatchResult(null);
                  setCsvFile(null);
                }}
                className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-semibold rounded-xl"
              >
                <span>Generate Another Batch</span>
              </button>
              <Link
                to="/admin/dashboard/generation-history"
                className="px-4 py-2.5 bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold rounded-xl shadow-sm inline-flex items-center gap-2"
              >
                <span>View Full Generation History</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Preview Certificate Image */}
      {previewUrl && (
        <div ref={previewDialogRef} role="dialog" aria-modal="true" aria-label="Personalized certificate preview" tabIndex={-1} className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm animate-in fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-3xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Eye className="w-5 h-5 text-teal-600" />
                  <span>Personalized Certificate Preview</span>
                </h3>
                <p className="text-xs text-slate-500">
                  Actual Pillow rendered PNG output using template background & typography
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPreviewUrl(null)}
                aria-label="Close certificate preview"
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-slate-950 flex items-center justify-center p-2">
              <img
                src={previewUrl}
                alt="Certificate Preview"
                className="max-h-[500px] w-auto object-contain rounded shadow-lg"
              />
            </div>

            <div className="flex items-center justify-between text-xs pt-2">
              <span className="text-slate-500">
                Signatures, seals, and OneSmarter, Inc. gold medal are preserved in the background design.
              </span>
              <button
                type="button"
                onClick={() => setPreviewUrl(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-xl font-semibold"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
      {editingTemplate && <TemplateLayoutEditor template={editingTemplate} onClose={() => setEditingTemplate(null)} onSaved={(updated) => {
        setTemplates((items) => items.map((item) => item.id === updated.id ? updated : item));
      }} />}
    </div>
  );
}
