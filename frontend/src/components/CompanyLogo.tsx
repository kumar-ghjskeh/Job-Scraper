import { useState } from 'react'

// Known company → primary domain (for logo fetch). Unknown → letter fallback.
const DOMAINS: Record<string, string> = {
  'nvidia': 'nvidia.com', 'intel': 'intel.com', 'marvell': 'marvell.com', 'micron': 'micron.com',
  'nxp semiconductors': 'nxp.com', 'analog devices': 'analog.com', 'astera labs': 'asteralabs.com',
  'tenstorrent': 'tenstorrent.com', 'cerebras systems': 'cerebras.net', 'sambanova systems': 'sambanova.ai',
  'lightmatter': 'lightmatter.co', 'ventana micro systems': 'ventanamicro.com',
  'lattice semiconductor': 'latticesemi.com', 'matx': 'matx.com', 'lemurian labs': 'lemurianlabs.com',
  'baya systems': 'bayasystems.com', 'eliyan': 'eliyan.com', 'd-matrix': 'd-matrix.ai',
  'etched': 'etched.com', 'rain ai': 'rain.ai', 'axelera ai': 'axelera.ai', 'amd': 'amd.com',
  'qualcomm': 'qualcomm.com', 'apple': 'apple.com', 'google': 'google.com', 'microsoft': 'microsoft.com',
  'meta': 'meta.com', 'amazon': 'amazon.com', 'arm': 'arm.com', 'synopsys': 'synopsys.com',
  'cadence': 'cadence.com', 'cisco': 'cisco.com', 'broadcom': 'broadcom.com',
  'samsung semiconductor': 'samsung.com', 'western digital': 'westerndigital.com', 'sifive': 'sifive.com',
  'groq': 'groq.com', 'arista networks': 'arista.com', 'synaptics': 'synaptics.com',
  'achronix': 'achronix.com', 'alphawave semi': 'awaveip.com', 'siemens eda': 'siemens.com',
}

interface Props {
  company: string
  size?: number
  radius?: number
}

export function CompanyLogo({ company, size = 46, radius = 10 }: Props) {
  const [failed, setFailed] = useState(false)
  const domain = DOMAINS[company.toLowerCase().trim()]
  const letter = company.charAt(0).toUpperCase()

  const fallback = (
    <div style={{
      width: size, height: size, borderRadius: radius, background: 'var(--primary-light)',
      border: '1px solid var(--primary-mid)', display: 'flex', alignItems: 'center',
      justifyContent: 'center', fontSize: size * 0.4, fontWeight: 800, color: 'var(--primary)',
      flexShrink: 0, letterSpacing: '-0.02em',
    }}>
      {letter}
    </div>
  )

  if (!domain || failed) return fallback

  return (
    <div style={{
      width: size, height: size, borderRadius: radius, background: '#FFFFFF',
      border: '1px solid var(--border)', display: 'flex', alignItems: 'center',
      justifyContent: 'center', flexShrink: 0, overflow: 'hidden',
    }}>
      <img
        src={`https://logo.clearbit.com/${domain}?size=128`}
        alt={company}
        width={size * 0.72} height={size * 0.72}
        style={{ objectFit: 'contain' }}
        onError={() => setFailed(true)}
        loading="lazy"
      />
    </div>
  )
}
