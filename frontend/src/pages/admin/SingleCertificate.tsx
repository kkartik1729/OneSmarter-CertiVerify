import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Sparkles,
  Eye,
  CheckCircle2,
  RefreshCw,
  Search,
  UserCheck,
  FileStack,
  ArrowRight,
} from 'lucide-react';
import {
  courseService,
  templateService,
  generationService,
  adminUsersService,
  errMsg,
} from '../../services';
import type { Course, CertificateTemplate, AdminUser, Cert } from '../../types';
import ErrorMessage from '../../components/ErrorMessage';
import LoadingSkeleton from '../../components/LoadingSkeleton';

export default function SingleCertificate() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [templates, setTemplates] = useState<CertificateTemplate[]>([]);
  const [loadingInitial, setLoadingInitial] = useState(true);

  // Form inputs
  const [selectedCourseId, setSelectedCourseId] = useState<number | ''>('');
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | ''>('');
  const [studentSearch, setStudentSearch] = useState('');
  const [searchResults, setSearchResults] = useState<AdminUser[]>([]);
  const [searchingStudents, setSearchingStudents] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<AdminUser | null>(null);

  const [studentDisplayName, setStudentDisplayName] = useState('');
  const [studentNameError, setStudentNameError] = useState<string | null>(null);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [issueDate, setIssueDate] = useState(new Date().toISOString().slice(0, 10));

  // Preview & Submission
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [createdCert, setCreatedCert] = useState<Cert | null>(null);

  // Alerts
  const [error, setError] = useState<string | null>(null);

  // Initial load
  useEffect(() => {
    const init = async () => {
      setLoadingInitial(true);
      setError(null);
      try {
        const [cList, tList] = await Promise.all([
          courseService.list(),
          templateService.list(),
        ]);
        setCourses(cList);
        setTemplates(tList);
        if (cList.length > 0) {
          setSelectedCourseId(cList[0].id);
          setStartDate(cList[0].start_date);
          setEndDate(cList[0].end_date);
        }
        if (tList.length > 0) {
          setSelectedTemplateId(tList[0].id);
        }
      } catch (err) {
        setError(errMsg(err));
      } finally {
        setLoadingInitial(false);
      }
    };
    init();
  }, []);

  // Update dates when course selection changes
  const handleCourseChange = (courseId: number) => {
    setSelectedCourseId(courseId);
    const found = courses.find((c) => c.id === courseId);
    if (found) {
      setStartDate(found.start_date);
      setEndDate(found.end_date);
    }
  };

  // Search students
  const handleSearchStudents = async (query: string) => {
    setStudentSearch(query);
    if (!query.trim() || query.trim().length < 2) {
      setSearchResults([]);
      return;
    }
    setSearchingStudents(true);
    try {
      const res = await adminUsersService.list({ search: query.trim() });
      setSearchResults(res);
    } catch (err) {
      console.error('Error searching students:', err);
    } finally {
      setSearchingStudents(false);
    }
  };

  const handleSelectStudent = (u: AdminUser) => {
    setSelectedStudent(u);
    const fullName = `${u.first_name} ${u.last_name}`.trim() || u.username;
    setStudentDisplayName(fullName);
    setSearchResults([]);
    setStudentSearch(`${fullName} (${u.email})`);
  };

  // Live preview
  const handlePreview = async () => {
    if (!selectedTemplateId) {
      setError('Please select a certificate template to preview.');
      return;
    }
    const c = courses.find((course) => course.id === Number(selectedCourseId));
    setLoadingPreview(true);
    setError(null);
    try {
      const res = await generationService.preview({
        template_id: Number(selectedTemplateId),
        student_name: studentDisplayName.trim() || 'Student Name',
        course_name: c?.name || 'Course Name',
        start_date: startDate || '2026-07-01',
        end_date: endDate || '2026-10-01',
        issue_date: issueDate || new Date().toISOString().slice(0, 10),
        issuer_name: c?.issuer || 'OneSmarter, Inc.',
      });
      setPreviewUrl(res.preview_url);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoadingPreview(false);
    }
  };

  // Generate certificate
  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCourseId) {
      setError('Please select a course.');
      return;
    }
    if (!selectedTemplateId) {
      setError('Please select a certificate template.');
      return;
    }
    if (!selectedStudent) {
      setError('Please search and select a registered student account.');
      return;
    }
    const trimmedName = studentDisplayName.trim();
    if (!trimmedName) {
      setStudentNameError('Student name is required.');
      setError('Please enter the student recipient name as it should appear on the certificate.');
      return;
    }
    if (trimmedName.length >= 30) {
      const msg = `Student name must be 1–29 characters (currently ${trimmedName.length} characters: "${trimmedName}").`;
      setStudentNameError(msg);
      setError(msg);
      return;
    }
    setStudentNameError(null);

    if (!startDate || !endDate || !issueDate) {
      setError('Start date, end date, and issue date are required.');
      return;
    }
    if (endDate < startDate) {
      setError('Course end date cannot be earlier than start date.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const cert = await generationService.singleGenerate({
        course_id: Number(selectedCourseId),
        template_id: Number(selectedTemplateId),
        user_id: selectedStudent.id,
        student_email: selectedStudent.email,
        student_name: trimmedName,
        start_date: startDate,
        end_date: endDate,
        issue_date: issueDate,
      });
      setCreatedCert(cert);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (loadingInitial) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton lines={4} height="h-10" />
        <LoadingSkeleton lines={6} height="h-16" />
      </div>
    );
  }

  const selectedCourse = courses.find((c) => c.id === Number(selectedCourseId));
  const selectedTemplate = templates.find((t) => t.id === Number(selectedTemplateId));

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-6 sm:p-8 text-white shadow-md border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <span className="text-teal-400 font-semibold text-xs tracking-wider uppercase bg-teal-950/60 border border-teal-800/80 px-2.5 py-1 rounded-full">
            On-Demand Issuance
          </span>
          <h2 className="text-2xl font-bold tracking-tight mt-2.5 flex items-center gap-3">
            <Sparkles className="w-7 h-7 text-teal-400" />
            <span>Generate Single Certificate</span>
          </h2>
          <p className="text-slate-300 text-sm mt-1 max-w-xl">
            Issue a personalized certificate directly for a registered student without uploading a CSV. The certificate is stored in PostgreSQL and sent via email notification.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link
            to="/admin/dashboard/generate"
            className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-sm font-semibold transition inline-flex items-center gap-2"
          >
            <FileStack className="w-4 h-4 text-teal-400" />
            <span>Bulk Generation</span>
          </Link>
        </div>
      </div>

      {error && <ErrorMessage message={error} onRetry={() => setError(null)} />}

      {/* Success Dialog */}
      {createdCert && (
        <div className="p-6 bg-teal-50 dark:bg-teal-950/50 border border-teal-200 dark:border-teal-800 rounded-2xl shadow-sm space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-teal-600 text-white rounded-xl">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-teal-900 dark:text-teal-200">
                Certificate Generated & Issued Successfully!
              </h3>
              <p className="text-xs text-teal-700 dark:text-teal-300 font-mono mt-0.5">
                Certificate Number: {createdCert.number} · Recipient: {createdCert.recipient}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            {createdCert.imageUrl && (
              <a
                href={createdCert.imageUrl}
                target="_blank"
                rel="noreferrer"
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl shadow-sm inline-flex items-center gap-1.5"
              >
                <Eye className="w-3.5 h-3.5" />
                <span>View Generated Certificate Image</span>
              </a>
            )}
            <button
              type="button"
              onClick={() => {
                setCreatedCert(null);
                setSelectedStudent(null);
                setStudentSearch('');
                setStudentDisplayName('');
              }}
              className="px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 font-semibold text-xs rounded-xl hover:bg-slate-50"
            >
              Generate Another
            </button>
            <Link
              to="/admin/dashboard/certificates"
              className="px-4 py-2 bg-slate-800 text-white font-semibold text-xs rounded-xl hover:bg-slate-700 ml-auto inline-flex items-center gap-1.5"
            >
              <span>Manage Certificates</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      )}

      {/* Form Card */}
      {!createdCert && (
        <form onSubmit={handleGenerate} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-8 shadow-sm space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
            {/* 1. Course Selection */}
            <div className="space-y-2">
              <label className="block font-semibold text-slate-700 dark:text-slate-300">
                1. Select Course *
              </label>
              <select
                required
                value={selectedCourseId}
                onChange={(e) => handleCourseChange(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} — {c.issuer}
                  </option>
                ))}
              </select>
              {selectedCourse && (
                <p className="text-[11px] text-slate-500">
                  Certificate Title: {selectedCourse.title}
                </p>
              )}
            </div>

            {/* 2. Certificate Template */}
            <div className="space-y-2">
              <label className="block font-semibold text-slate-700 dark:text-slate-300">
                2. Select Certificate Template *
              </label>
              <select
                required
                value={selectedTemplateId}
                onChange={(e) => setSelectedTemplateId(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
              {selectedTemplate && selectedTemplate.image_url && (
                <div className="flex items-center gap-3 pt-1">
                  <img
                    src={selectedTemplate.image_url}
                    alt={selectedTemplate.name}
                    className="w-16 h-10 object-cover rounded border border-slate-200"
                  />
                  <span className="text-[11px] text-slate-500">Template background active</span>
                </div>
              )}
            </div>

            {/* 3. Search and select registered student */}
            <div className="space-y-2 relative md:col-span-2">
              <label className="block font-semibold text-slate-700 dark:text-slate-300">
                3. Search and Select Registered Student (by name or email) *
              </label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="Type student name or email to search..."
                  value={studentSearch}
                  onChange={(e) => handleSearchStudents(e.target.value)}
                  className="w-full pl-9 pr-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                {searchingStudents && (
                  <RefreshCw className="w-4 h-4 text-teal-600 animate-spin absolute right-3 top-3" />
                )}
              </div>

              {/* Autocomplete dropdown */}
              {searchResults.length > 0 && (
                <div className="absolute z-20 top-full left-0 right-0 mt-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg max-h-48 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-700">
                  {searchResults.map((u) => (
                    <button
                      key={u.id}
                      type="button"
                      onClick={() => handleSelectStudent(u)}
                      className="w-full px-4 py-2.5 text-left hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center justify-between text-xs"
                    >
                      <div>
                        <p className="font-semibold text-slate-900 dark:text-white">
                          {u.first_name} {u.last_name} ({u.username})
                        </p>
                        <p className="text-slate-500 font-mono text-[11px]">{u.email}</p>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 dark:bg-slate-600 text-slate-700 dark:text-slate-200">
                        Select
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {selectedStudent ? (
                <div className="p-3 bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 rounded-xl text-xs flex items-center gap-3">
                  <UserCheck className="w-5 h-5 text-teal-600" />
                  <div>
                    <span className="font-semibold text-teal-900 dark:text-teal-200">
                      Selected Student Account:
                    </span>{' '}
                    <span>{selectedStudent.first_name} {selectedStudent.last_name} ({selectedStudent.email})</span>
                  </div>
                </div>
              ) : (
                <p className="text-[11px] text-slate-500">
                  * Note: Only registered accounts can be issued certificates. Unregistered users must register first.
                </p>
              )}
            </div>

            {/* 4. Student Name as it will appear */}
            <div className="space-y-2 md:col-span-2">
              <div className="flex items-center justify-between">
                <label className="block font-semibold text-slate-700 dark:text-slate-300">
                  4. Recipient Name (As printed on certificate) *
                </label>
                <span className={`text-[11px] font-medium ${studentDisplayName.trim().length >= 30 ? 'text-rose-500 font-bold' : 'text-slate-400'}`}>
                  {studentDisplayName.trim().length} / 29 characters max
                </span>
              </div>
              <input
                type="text"
                required
                placeholder="e.g. Kartik Hande (1–29 characters)"
                value={studentDisplayName}
                onChange={(e) => {
                  const val = e.target.value;
                  setStudentDisplayName(val);
                  const trimmed = val.trim();
                  if (trimmed.length >= 30) {
                    setStudentNameError(`Student name must be 1–29 characters (currently ${trimmed.length} characters).`);
                  } else {
                    setStudentNameError(null);
                  }
                }}
                className={`w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border rounded-xl text-slate-900 dark:text-white focus:outline-none focus:ring-2 ${
                  studentNameError
                    ? 'border-rose-400 focus:ring-rose-500'
                    : 'border-slate-300 dark:border-slate-700 focus:ring-teal-500'
                }`}
              />
              {studentNameError && (
                <p className="text-xs text-rose-600 dark:text-rose-400 font-medium mt-1">
                  {studentNameError}
                </p>
              )}
            </div>

            {/* 5. Dates */}
            <div className="space-y-2">
              <label className="block font-semibold text-slate-700 dark:text-slate-300">
                5. Course Start Date *
              </label>
              <input
                type="date"
                required
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>

            <div className="space-y-2">
              <label className="block font-semibold text-slate-700 dark:text-slate-300">
                6. Course End Date *
              </label>
              <input
                type="date"
                required
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>

            <div className="space-y-2">
              <label className="block font-semibold text-slate-700 dark:text-slate-300">
                7. Certificate Issue Date *
              </label>
              <input
                type="date"
                required
                value={issueDate}
                onChange={(e) => setIssueDate(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>
          </div>

          {/* Buttons: Preview & Generate */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-200 dark:border-slate-800">
            <button
              type="button"
              disabled={loadingPreview || !selectedTemplateId}
              onClick={handlePreview}
              className="w-full sm:w-auto px-4 py-2.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-semibold rounded-xl text-xs inline-flex items-center justify-center gap-2"
            >
              <Eye className="w-4 h-4 text-teal-600" />
              <span>{loadingPreview ? 'Rendering Preview...' : 'Preview Certificate'}</span>
            </button>

            <button
              type="submit"
              disabled={submitting}
              className="w-full sm:w-auto px-6 py-2.5 bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-white font-semibold rounded-xl text-xs inline-flex items-center justify-center gap-2 shadow-sm transition"
            >
              {submitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Generating & Saving...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Generate Certificate</span>
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {/* Preview Modal */}
      {previewUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm animate-in fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-3xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Eye className="w-5 h-5 text-teal-600" />
                  <span>Personalized Certificate Preview</span>
                </h3>
                <p className="text-xs text-slate-500">
                  Pillow rendering preview for recipient &quot;{studentDisplayName}&quot;
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPreviewUrl(null)}
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

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setPreviewUrl(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-xl text-xs font-semibold"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
