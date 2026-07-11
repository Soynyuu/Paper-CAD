import { motion, useReducedMotion } from 'framer-motion';
import {
  ArrowRight,
  Box,
  Building2,
  Check,
  FileCode2,
  FileText,
  Github,
  Layers3,
  Printer,
} from 'lucide-react';

const githubUrl = 'https://github.com/kodaimiyazaki/Paper-CAD';

const workflow = [
  {
    number: '01',
    name: 'Model',
    title: '建物を読み込む',
    body: 'STEPやCityGML、PLATEAUの都市データから、模型にしたい建物を用意します。',
    icon: Building2,
  },
  {
    number: '02',
    name: 'Unfold',
    title: '展開図をつくる',
    body: '3D形状を解析し、切り線・折り線・のりしろを備えた展開図を生成します。',
    icon: Layers3,
  },
  {
    number: '03',
    name: 'Print',
    title: '紙に出力する',
    body: 'SVGまたはPDFで保存。A4・A3・Letterの用紙に合わせて印刷できます。',
    icon: Printer,
  },
  {
    number: '04',
    name: 'Build',
    title: '組み立てる',
    body: '切って、折って、貼り合わせる。画面の中の建物が、手のひらに立ち上がります。',
    icon: Box,
  },
];

const formats = [
  { name: 'STEP', detail: '.step / .stp', type: 'INPUT' },
  { name: 'CityGML', detail: '.gml / .xml', type: 'INPUT' },
  { name: 'PLATEAU', detail: '3D都市モデル', type: 'INPUT' },
  { name: 'SVG', detail: '編集可能なベクター', type: 'OUTPUT' },
  { name: 'PDF', detail: '印刷用ドキュメント', type: 'OUTPUT' },
];

const recognition = [
  { year: '2025', title: '未踏ジュニア 採択' },
  { year: '2024', title: 'アプリ甲子園 優勝' },
  { year: '2024', title: 'アプリ甲子園 技術賞' },
  { year: '2024', title: 'アプリ甲子園 Cygames賞' },
];

function Logo() {
  return (
    <a className="logo" href="#top" aria-label="PaperCAD トップへ">
      <span className="logo-mark" aria-hidden="true" />
      <span>PaperCAD</span>
    </a>
  );
}

function LaunchLink({ className = '' }: { className?: string }) {
  return (
    <a className={`button button-primary ${className}`} href="/app">
      PaperCADを開く
      <ArrowRight size={17} aria-hidden="true" />
    </a>
  );
}

function Header() {
  return (
    <header className="site-header">
      <div className="shell header-inner">
        <Logo />
        <nav className="desktop-nav" aria-label="メインナビゲーション">
          <a href="#workflow">使い方</a>
          <a href="#formats">対応形式</a>
          <a href="#product">プロダクト</a>
          <a href="#assembly">組み立てモード</a>
          <a href="#recognition">受賞・採択</a>
        </nav>
        <LaunchLink className="header-cta" />
      </div>
    </header>
  );
}

function Hero() {
  const reduceMotion = useReducedMotion();
  const reveal = reduceMotion
    ? {}
    : { initial: { opacity: 0, y: 24 }, animate: { opacity: 1, y: 0 } };

  return (
    <main id="top">
      <section className="hero section-grid">
        <div className="shell hero-grid">
          <motion.div
            className="hero-copy"
            {...reveal}
            transition={{ duration: 0.75, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="eyebrow">PAPER MODEL CAD / BROWSER BASED</p>
            <h1>
              簡単な、<br />
              高精度な<span>模型のまちづくり</span>を。
            </h1>
            <p className="hero-definition">
              PaperCADは、<strong>建物模型を自作するとき</strong>の
              <strong>大変な設計作業</strong>を簡単にするためのソフトウェアです。
            </p>
            <div className="hero-actions">
              <LaunchLink />
              <a className="button button-secondary" href={githubUrl} target="_blank" rel="noreferrer">
                <Github size={17} aria-hidden="true" />
                GitHubを見る
              </a>
            </div>
            <p className="micro-copy">ブラウザですぐに使えます。インストール不要。</p>
          </motion.div>

          <motion.figure
            className="hero-visual"
            initial={reduceMotion ? false : { opacity: 0, scale: 0.985 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
          >
            <img
              src="/images/paper-cad-workflow.png"
              alt="PaperCADで建物の3Dモデルと展開図を設計し、白い紙模型として組み立てた様子"
            />
            <figcaption>
              <span>MODEL</span>
              <span className="transform-line">3D → 2D → PAPER</span>
              <span>BUILD</span>
            </figcaption>
          </motion.figure>
        </div>
        <div className="hero-spec" aria-hidden="true">
          <span>FORMAT / A3</span>
          <span>UNIT / MM</span>
          <span>OUTPUT / SVG · PDF</span>
        </div>
      </section>

      <WorkflowSection />
      <FormatsSection />
      <ProductSection />
      <AssemblySection />
      <RecognitionSection />
      <ClosingSection />
    </main>
  );
}

function SectionHeading({ index, label, title }: { index: string; label: string; title: string }) {
  return (
    <div className="section-heading">
      <div>
        <span className="section-index">{index}</span>
        <span className="section-label">{label}</span>
      </div>
      <h2>{title}</h2>
    </div>
  );
}

function WorkflowSection() {
  return (
    <section className="content-section" id="workflow">
      <div className="shell">
        <SectionHeading index="01" label="WORKFLOW" title="設計から、組み立てまで。" />
        <div className="workflow-grid">
          {workflow.map((step) => {
            const Icon = step.icon;
            return (
              <article className="workflow-step" key={step.name}>
                <div className="step-meta">
                  <span>{step.number}</span>
                  <span>{step.name}</span>
                </div>
                <Icon className="step-icon" strokeWidth={1.25} aria-hidden="true" />
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function FormatsSection() {
  return (
    <section className="content-section formats-section" id="formats">
      <div className="shell">
        <SectionHeading index="02" label="FORMAT" title="都市データから、印刷データへ。" />
        <div className="formats-layout">
          <div className="formats-list">
            {formats.map((format) => (
              <div className="format-row" key={format.name}>
                <span className="format-type">{format.type}</span>
                <strong>{format.name}</strong>
                <span>{format.detail}</span>
                <Check size={16} aria-label="対応済み" />
              </div>
            ))}
          </div>
          <div className="formats-note">
            <FileCode2 size={28} strokeWidth={1.25} aria-hidden="true" />
            <p className="quote">展開図は、変換ではなく翻訳だ。</p>
            <p>
              面のつながりを読み取り、切り線・折り線・のりしろへ。3Dの構造を、紙で組み立てられる情報に翻訳します。
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function ProductSection() {
  return (
    <section className="content-section product-section" id="product">
      <div className="shell">
        <SectionHeading index="03" label="PRODUCT" title="ブラウザで完結する、模型専用CAD。" />
        <div className="product-layout">
          <div className="product-copy">
            <p>
              モデリング、建物データの読み込み、展開、レイアウト、出力までをひとつの画面で。複雑だった模型設計を、試せる工程に変えます。
            </p>
            <ul>
              <li>OpenCASCADEによる精密な形状処理</li>
              <li>折り線・切り線・面番号を自動生成</li>
              <li>A4 / A3 / Letterのページレイアウト</li>
              <li>SVG / PDFの印刷用データ出力</li>
            </ul>
          </div>
          <figure className="product-screen">
            <img src="/images/footer-brand.png" alt="PaperCADのスタート画面。新規模型、保存済みファイル、建物名や住所から模型を作成できる" />
            <figcaption>
              <span>ACTUAL INTERFACE</span>
              <span>WEB APPLICATION / JA</span>
            </figcaption>
          </figure>
        </div>
      </div>
    </section>
  );
}

function AssemblySection() {
  return (
    <section className="content-section assembly-section" id="assembly">
      <div className="shell">
        <SectionHeading index="04" label="ASSEMBLY MODE" title="紙と画面を、切り離さない。" />
        <div className="assembly-layout">
          <div className="assembly-intro">
            <p className="assembly-kicker">A NEW WAY TO BUILD</p>
            <h3>「この紙の面は、建物のどこ？」を画面に聞ける。</h3>
            <p>
              模型づくりで迷いやすいのは、切り出したパーツと元の建物の対応です。組み立てモードでは、3Dモデルと2D展開図を並べ、面番号を入力したり面を選んだりして、対応する場所を確認できます。
            </p>
            <p>
              印刷して終わるCADではなく、紙を切り、折り、貼る時間までデジタルが支える。ソフトウェアだからこそ実現できる、新しい模型の組み立て体験です。
            </p>
          </div>
          <div className="assembly-flow" aria-label="組み立てモードで3Dモデルと2D展開図の面を照合する流れ">
            <div className="assembly-flow-item">
              <span>01 / FIND</span>
              <Building2 strokeWidth={1.2} aria-hidden="true" />
              <strong>3Dモデル</strong>
              <p>建物上の面を選ぶ</p>
            </div>
            <ArrowRight className="assembly-arrow" aria-hidden="true" />
            <div className="assembly-face-number">
              <span>FACE</span>
              <strong>128</strong>
              <span>SELECTED</span>
            </div>
            <ArrowRight className="assembly-arrow" aria-hidden="true" />
            <div className="assembly-flow-item">
              <span>02 / MATCH</span>
              <FileCode2 strokeWidth={1.2} aria-hidden="true" />
              <strong>2D展開図</strong>
              <p>対応するパーツを確認</p>
            </div>
          </div>
        </div>
        <p className="assembly-note">3Dと2Dの面番号を照合・ハイライトする機能を搭載。QR連携など将来機能は含みません。</p>
      </div>
    </section>
  );
}

function RecognitionSection() {
  return (
    <section className="content-section" id="recognition">
      <div className="shell">
        <SectionHeading index="05" label="RECOGNITION" title="受賞・採択" />
        <div className="recognition-list">
          {recognition.map((item) => (
            <div className="recognition-item" key={item.title}>
              <span>{item.year}</span>
              <strong>{item.title}</strong>
              <span className="recognition-rule" />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ClosingSection() {
  return (
    <section className="closing-section">
      <div className="shell closing-grid">
        <div>
          <p className="eyebrow">FROM DIGITAL SHAPE TO PHYSICAL FORM</p>
          <h2>今日のモデルを、<br />紙のかたちに。</h2>
        </div>
        <div className="closing-actions">
          <LaunchLink />
          <p>紙は、終わりではない。紙はインターフェースだ。</p>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="site-footer">
      <div className="shell footer-inner">
        <Logo />
        <p>© 2026 PaperCAD</p>
        <a href={githubUrl} target="_blank" rel="noreferrer">
          <Github size={15} aria-hidden="true" />
          GitHub
        </a>
        <span className="footer-format">
          <FileText size={14} aria-hidden="true" /> SVG / PDF
        </span>
      </div>
    </footer>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#top">本文へ移動</a>
      <Header />
      <Hero />
      <Footer />
    </div>
  );
}
