import { useEffect, useState } from 'react'

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
  'waymo': 'waymo.com',
  // Remaining tracked companies (so every card shows a real logo)
  'bae systems': 'baesystems.com', 'celestial ai': 'celestial.ai',
  'cornelis networks': 'cornelisnetworks.com', 'credo semiconductor': 'credosemi.com',
  'enfabrica': 'enfabrica.net', 'esperanto technologies': 'esperanto.ai',
  'general dynamics mission systems': 'gd.com', 'juniper networks': 'juniper.net',
  'keysight technologies': 'keysight.com', 'maxlinear': 'maxlinear.com',
  'microchip technology': 'microchip.com', 'rtx': 'rtx.com', 'rambus': 'rambus.com',
  'seagate': 'seagate.com', 'texas instruments': 'ti.com', 'untether ai': 'untether.ai',
  'hcltech': 'hcltech.com', 'wipro': 'wipro.com', 'mediatek': 'mediatek.com',
  // Expanded directory (75+ companies)
  'globalfoundries': 'gf.com', 'renesas electronics': 'renesas.com',
  'infineon technologies': 'infineon.com', 'stmicroelectronics': 'st.com',
  'cadence design systems': 'cadence.com', 'skyworks solutions': 'skyworksinc.com',
  'qorvo': 'qorvo.com', 'onsemi': 'onsemi.com', 'cirrus logic': 'cirrus.com',
  'silicon labs': 'silabs.com', 'ambarella': 'ambarella.com', 'wolfspeed': 'wolfspeed.com',
  'teradyne': 'teradyne.com', 'ampere computing': 'amperecomputing.com', 'kioxia': 'kioxia.com',
  'sk hynix': 'skhynix.com', 'tsmc': 'tsmc.com', 'ayar labs': 'ayarlabs.com',
  'rivos': 'rivosinc.com', 'sima.ai': 'sima.ai', 'recogni': 'recogni.com',
  'mythic': 'mythic.ai', 'blaize': 'blaize.com', 'flex logix': 'flex-logix.com',
  'quadric': 'quadric.io', 'expedera': 'expedera.com', 'tesla': 'tesla.com',
  'boeing': 'boeing.com', 'honeywell': 'honeywell.com', 'collins aerospace': 'collinsaerospace.com',
  // Added 2026-10-07 for the expanded directory. The ones with a company-owned
  // careers_url are DERIVED from it, so they match a URL that was verified to
  // answer; the rest were checked by hand. A wrong domain shows another firm's
  // logo, which is worse than the letter tile, so none of these are guesses.
  'advantest': 'advantest.com', 'aeva': 'aeva.com', 'akeana': 'akeana.com',
  'allegro microsystems': 'allegromicro.com', 'ambiq': 'ambiq.com',
  'andes technology': 'andestech.com', 'applied materials': 'appliedmaterials.com',
  'arteris': 'arteris.com', 'atom computing': 'atom-computing.com', 'auradine': 'auradine.com',
  'axiado': 'axiado.com', 'breker verification systems': 'brekersystems.com',
  'ciena': 'ciena.com', 'codasip': 'codasip.com', 'dreambig semiconductor': 'dreambigsemi.com',
  'empower semiconductor': 'empowersemi.com', 'encharge ai': 'enchargeai.com',
  'ethernovia': 'ethernovia.com', 'etopus': 'etopus.com', 'formfactor': 'formfactor.com',
  'furiosaai': 'furiosa.ai', 'graphcore': 'graphcore.ai', 'hailo': 'hailo.ai',
  'hewlett packard enterprise': 'hpe.com', 'ibm': 'ibm.com',
  'imagination technologies': 'imaginationtech.com', 'indie semiconductor': 'indiesemi.com',
  'infleqtion': 'infleqtion.com', 'ionq': 'ionq.com', 'kla': 'kla.com', 'mips': 'mips.com',
  'mobileye': 'mobileye.com', 'monolithic power systems': 'monolithicpower.com',
  'movellus': 'movellus.com', 'navitas semiconductor': 'navitassemi.com', 'nokia': 'nokia.com',
  'normal computing': 'normalcomputing.ai', 'nubis communications': 'nubis-inc.com',
  'nutanix': 'nutanix.com', 'oracle': 'oracle.com', 'phison': 'phison.com',
  'power integrations': 'power.com', 'psiquantum': 'psiquantum.com',
  'pure storage': 'purestorage.com', 'quantinuum': 'quantinuum.com',
  'real intent': 'realintent.com', 'rebellions': 'rebellions.ai',
  'recogni (tensordyne)': 'tensordyne.ai', 'rigetti computing': 'rigetti.com',
  'sandisk': 'sandisk.com', 'semidynamics': 'semidynamics.com', 'semtech': 'semtech.com',
  'silicon motion': 'siliconmotion.com', 'sitime': 'sitime.com', 'syntiant': 'syntiant.com',
  'taalas': 'taalas.com', 'tetramem': 'tetramem.com'
}

// Resilient logo sources, tried in order. icon.horse returns the real brand logo
// for both giants and startups (Clearbit's old API is discontinued); Google's
// favicon service is the always-on fallback; then a letter tile.
function sources(domain: string): string[] {
  return [
    `https://icon.horse/icon/${domain}`,
    `https://www.google.com/s2/favicons?domain=${domain}&sz=128`,
  ]
}

interface Props {
  company: string
  size?: number
  radius?: number
}

export function CompanyLogo({ company, size = 46, radius = 10 }: Props) {
  const domain = DOMAINS[company.toLowerCase().trim()]
  const [stage, setStage] = useState(0)
  useEffect(() => { setStage(0) }, [domain])

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

  const urls = domain ? sources(domain) : []
  if (!domain || stage >= urls.length) return fallback

  return (
    <div style={{
      // --logo-tile, not hard white: vendor marks need a light backing, but a
      // pure-white square punches a hole in the dark page, so the shade has to
      // be tunable per theme. (--brand-tile is the DARK tile for our own logo.)
      width: size, height: size, borderRadius: radius, background: 'var(--logo-tile)',
      border: '1px solid var(--border)', display: 'flex', alignItems: 'center',
      justifyContent: 'center', flexShrink: 0, overflow: 'hidden',
    }}>
      <img
        key={stage}
        src={urls[stage]}
        alt={company}
        width={size * 0.74} height={size * 0.74}
        style={{ objectFit: 'contain' }}
        onError={() => setStage((s) => s + 1)}
        loading="lazy"
      />
    </div>
  )
}
