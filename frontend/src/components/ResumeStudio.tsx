import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import type { Job } from '../lib/types'
import { Icon } from './Icon'

// Master résumé + instructions are global (set once, reused for every job), so we
// cache them at module scope and only hit the API the first time.
let _master: { master_latex: string; instructions: string; gemini_enabled: boolean } | null = null

const sectionLabel: React.CSSProperties = {
  fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)',
  textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8, display: 'block',
}
const ta: React.CSSProperties = {
  width: '100%', border: '1px solid var(--border)', borderRadius: 8, padding: '9px 11px',
  fontSize: 12, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
  background: 'var(--surface)', color: 'var(--text-primary)', outline: 'none',
  resize: 'vertical', lineHeight: 1.5,
}

export function ResumeStudio({ job }: { job: Job }) {
  const [masterLatex, setMasterLatex] = useState('')
  const [instructions, setInstructions] = useState('')
  const [geminiEnabled, setGeminiEnabled] = useState(false)
  const [missing, setMissing] = useState<string[]>([])
  const [loadingKw, setLoadingKw] = useState(true)
  const [savedMaster, setSavedMaster] = useState(false)
  const [copied, setCopied] = useState(false)
  const [copyingPrompt, setCopyingPrompt] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [genLatex, setGenLatex] = useState('')
  const [genError, setGenError] = useState('')
  const [latexCopied, setLatexCopied] = useState(false)
  const loadedMaster = useRef(false)

  // Load the saved master résumé once per session.
  useEffect(() => {
    if (_master) {
      setMasterLatex(_master.master_latex); setInstructions(_master.instructions)
      setGeminiEnabled(_master.gemini_enabled); loadedMaster.current = true
      return
    }
    api.getMasterResume().then((m) => {
      _master = m
      setMasterLatex(m.master_latex); setInstructions(m.instructions); setGeminiEnabled(m.gemini_enabled)
      loadedMaster.current = true
    }).catch(() => { loadedMaster.current = true })
  }, [])

  // Per-job: fetch the keywords this role wants (accurate, bound to this job id).
  useEffect(() => {
    let cancelled = false
    setLoadingKw(true); setMissing([]); setGenLatex(''); setGenError('')
    api.getTailorPrompt(job.id, {})
      .then((r) => { if (!cancelled) setMissing(r.missing_keywords || []) })
      .catch(() => { if (!cancelled) setMissing([]) })
      .finally(() => { if (!cancelled) setLoadingKw(false) })
    return () => { cancelled = true }
  }, [job.id])

  async function saveMaster() {
    await api.saveMasterResume(masterLatex, instructions)
    _master = { master_latex: masterLatex, instructions, gemini_enabled: geminiEnabled }
    setSavedMaster(true); setTimeout(() => setSavedMaster(false), 2000)
  }

  async function copyPrompt() {
    setCopyingPrompt(true)
    try {
      const { prompt } = await api.getTailorPrompt(job.id, { master_latex: masterLatex, instructions })
      await navigator.clipboard.writeText(prompt)
      setCopied(true); setTimeout(() => setCopied(false), 2200)
    } finally { setCopyingPrompt(false) }
  }

  async function generate() {
    setGenerating(true); setGenError(''); setGenLatex('')
    try {
      const { latex } = await api.generateTailored(job.id, { master_latex: masterLatex, instructions })
      setGenLatex(latex)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setGenError(msg || 'Generation failed. Please try again.')
    } finally { setGenerating(false) }
  }

  function copyLatex() {
    navigator.clipboard.writeText(genLatex).then(() => {
      setLatexCopied(true); setTimeout(() => setLatexCopied(false), 2200)
    })
  }

  const hasMaster = masterLatex.trim().length > 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{
        background: 'var(--primary-light)', border: '1px solid var(--primary-mid)',
        borderRadius: 8, padding: '9px 12px', fontSize: 12, color: 'var(--primary)', lineHeight: 1.6,
      }}>
        <strong>Résumé Studio</strong> tailors your résumé to <strong>this</strong> role — keeping your exact LaTeX template, integrating its keywords truthfully. Review &amp; compile the result in Overleaf.
      </div>

      {/* Keywords this role wants */}
      <div>
        <span style={sectionLabel}>Keywords this role wants</span>
        {loadingKw ? (
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Analyzing this job…</div>
        ) : missing.length ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {missing.map((k) => <span key={k} className="pill pill-warning" style={{ fontSize: 11 }}>{k}</span>)}
          </div>
        ) : (
          <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>Upload a résumé in <strong style={{ color: 'var(--primary)' }}>Resume Matches</strong> to see the exact gaps for this job — the tailoring still works from the job description.</div>
        )}
      </div>

      {/* Master résumé */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ ...sectionLabel, marginBottom: 0 }}>Your master résumé (LaTeX)</span>
          <button onClick={saveMaster} disabled={!hasMaster}
            style={{ background: 'none', border: 'none', color: hasMaster ? 'var(--primary)' : 'var(--text-tertiary)', fontSize: 11.5, fontWeight: 700, cursor: hasMaster ? 'pointer' : 'default', padding: 0, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <Icon name={savedMaster ? 'check' : 'bookmark'} size={12} /> {savedMaster ? 'Saved' : 'Save as my master'}
          </button>
        </div>
        <textarea value={masterLatex} onChange={(e) => setMasterLatex(e.target.value)} rows={7}
          placeholder="Paste your Overleaf résumé LaTeX here. Saved once and reused for every job — edit anytime." style={ta} />
        <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', marginTop: 4 }}>
          Stored once and reused for every job. Update it whenever your real résumé changes.
        </div>
      </div>

      {/* Optional instructions */}
      <div>
        <span style={sectionLabel}>Tailoring instructions (optional)</span>
        <textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={2}
          placeholder="e.g. Keep it to one page. Emphasize UVM and formal verification." style={{ ...ta, fontFamily: 'inherit', fontSize: 12.5 }} />
      </div>

      {/* Option 1 — hand-off */}
      <div style={{ background: 'var(--surface-muted)', border: '1px solid var(--border)', borderRadius: 10, padding: '13px 14px' }}>
        <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          1 · Tailor with Claude or ChatGPT
        </div>
        <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginBottom: 10, lineHeight: 1.6 }}>
          Click <strong>Copy prompt</strong> — it copies a complete instruction (this job's details + your master résumé) to your clipboard. Then click <strong>Open Claude</strong> or <strong>Open ChatGPT</strong> to start a new chat, paste it (<strong>Ctrl + V</strong>), and press Enter. The AI replies with your tailored résumé written in LaTeX — copy that and paste it into Overleaf to compile.
        </div>
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
          <button onClick={copyPrompt} disabled={copyingPrompt} className="btn btn-primary" style={{ fontSize: 12.5 }}>
            <Icon name={copied ? 'check' : 'copy'} size={14} color="var(--on-primary)" /> {copied ? 'Prompt copied' : copyingPrompt ? 'Preparing…' : 'Copy prompt'}
          </button>
          <a href="https://claude.ai/new" target="_blank" rel="noopener noreferrer" className="btn btn-outline" style={{ fontSize: 12.5, textDecoration: 'none' }}>
            Open Claude <Icon name="external" size={13} />
          </a>
          <a href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer" className="btn btn-outline" style={{ fontSize: 12.5, textDecoration: 'none' }}>
            Open ChatGPT <Icon name="external" size={13} />
          </a>
        </div>
      </div>

      {/* Option 2 — in-app */}
      <div style={{ background: 'var(--surface-muted)', border: '1px solid var(--border)', borderRadius: 10, padding: '13px 14px' }}>
        <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          2 · Generate here in the app
        </div>
        {geminiEnabled ? (
          <>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginBottom: 10, lineHeight: 1.6 }}>
              Click <strong>Generate</strong> and the app writes your tailored résumé as LaTeX in the box below — you never leave the app. When it finishes, click <strong>Copy LaTeX</strong> and paste it into Overleaf to compile.
            </div>
            <button onClick={generate} disabled={generating || !hasMaster} className="btn btn-primary" style={{ fontSize: 12.5 }}>
              <Icon name="sparkles" size={14} color="var(--on-primary)" /> {generating ? 'Generating…' : 'Generate with Gemini'}
            </button>
            {!hasMaster && <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 8 }}>Paste your master résumé first.</span>}
            {genError && (
              <div style={{ marginTop: 10, fontSize: 12, color: 'var(--warning)', background: 'var(--warning-light)', border: '1px solid var(--warning-border)', borderRadius: 7, padding: '8px 10px' }}>{genError}</div>
            )}
            {genLatex && (
              <div style={{ marginTop: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <span style={{ ...sectionLabel, marginBottom: 0 }}>Tailored LaTeX</span>
                  <button onClick={copyLatex} style={{ background: 'none', border: 'none', color: 'var(--primary)', fontSize: 11.5, fontWeight: 700, cursor: 'pointer', padding: 0, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <Icon name={latexCopied ? 'check' : 'copy'} size={12} /> {latexCopied ? 'Copied' : 'Copy LaTeX'}
                  </button>
                </div>
                <textarea readOnly value={genLatex} rows={10} style={ta} />
              </div>
            )}
          </>
        ) : (
          <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            This button writes your tailored résumé as LaTeX without leaving the app, but it first needs a <strong>free Google Gemini API key</strong> (no credit card). Get one at <strong>aistudio.google.com/apikey</strong>, then add it to your backend as <code>GEMINI_API_KEY</code> and reopen the app. Until then, use <strong>option 1 above</strong> — it produces the same tailored résumé through your Claude or ChatGPT chat.
          </div>
        )}
      </div>
    </div>
  )
}
