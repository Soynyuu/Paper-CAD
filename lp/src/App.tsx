import { motion } from 'framer-motion';
import { 
  ArrowRight,
  Github,
  ChevronRight,
  Box,
  Layers,
  Cpu,
  Trophy,
  Gamepad2,
  Sparkles
} from 'lucide-react';

const easeOutExpo = [0.16, 1, 0.3, 1];

const fadeInUp = {
  initial: { opacity: 0, y: 40 },
  animate: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 1.2, ease: easeOutExpo }
  }
};

const staggerContainer = {
  animate: {
    transition: {
      staggerChildren: 0.15
    }
  }
};

export default function App() {
  return (
    <div className="min-h-screen bg-white text-[#111] font-sans overflow-x-hidden selection:bg-[#111] selection:text-white">
      
      {/* Structural Grid Decor */}
      <div className="fixed inset-0 pointer-events-none z-0 opacity-[0.03]">
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)', backgroundSize: '100px 100px' }}></div>
      </div>

      {/* Navbar */}
      <nav className="fixed w-full z-50 top-0 left-0 bg-white/80 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-[1440px] mx-auto px-8 h-24 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-[#111] rounded-full flex items-center justify-center text-white">
              <Box className="w-5 h-5" />
            </div>
            <div className="font-black text-2xl tracking-tighter uppercase">Paper—CAD</div>
          </div>
          <div className="flex items-center gap-12 text-[13px] font-black tracking-[0.2em] uppercase">
            <a href="https://github.com/kodaimiyazaki/Paper-CAD" target="_blank" rel="noreferrer" className="hidden lg:block hover:text-brand-orange transition-colors">GitHub</a>
            <a href="/app" className="group flex items-center gap-3 bg-[#111] text-white px-8 py-4 rounded-full hover:bg-brand-orange transition-all duration-500">
              Launch App
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </a>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-64 pb-48 px-8 lg:px-16 z-10">
        <div className="max-w-[1200px] mx-auto">
          <motion.div 
            initial="initial"
            animate="animate"
            variants={staggerContainer}
          >
            <motion.div variants={fadeInUp} className="mb-16 relative">
               <div className="absolute -left-12 top-0 h-full w-px bg-gray-200 hidden lg:block" />
               <span className="font-mono text-brand-orange text-[11px] font-bold tracking-[0.4em] block mb-10 uppercase">Computational Craft</span>
               <h1 className="text-7xl lg:text-[11rem] font-black tracking-[-0.04em] leading-[0.85] mb-12">
                 Unfold<br/>
                 the<br/>
                 <span className="text-brand-orange italic">World.</span>
               </h1>
            </motion.div>
            
            <motion.div variants={fadeInUp} className="max-w-3xl ml-auto lg:mr-24">
               <p className="text-xl lg:text-3xl leading-[1.6] font-bold tracking-[-0.02em] text-[#333]">
                 都市データを、展開図に。<br/>
                 3Dを、紙の模型へ。
               </p>
               <p className="text-lg lg:text-xl leading-relaxed text-gray-500 mt-8 tracking-normal font-medium">
                 Paper-CADは、建築・都市の3Dデータを、組み立てられるペーパーモデルへ変換する幾何エンジンです。PLATEAUの都市空間からSTEPの精密モデルまで、ブラウザ上で解析し、展開図を生成します。
               </p>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Section 01: Manifesto */}
      <section className="py-48 px-8 lg:px-16 border-t border-gray-100 bg-[#F9FAFB]">
        <div className="max-w-[1200px] mx-auto flex flex-col lg:flex-row gap-24 items-start">
          <div className="w-full lg:w-1/3 sticky top-48">
            <div className="flex flex-col gap-4">
              <span className="font-mono text-[11px] font-bold tracking-[0.4em] text-gray-400 uppercase">01 PHILOSOPHY</span>
              <h2 className="text-5xl font-black tracking-tighter leading-tight">
                世界を、<br/>
                手のひらに。
              </h2>
            </div>
          </div>
          <div className="w-full lg:w-2/3 space-y-16">
            <div className="space-y-8">
              <div className="w-12 h-1 bg-brand-orange"></div>
              <blockquote className="text-3xl lg:text-4xl font-black tracking-tight leading-tight text-gray-800">
                「我々が建物をつくり、<br/>やがて建物が我々をつくる。」
              </blockquote>
              <p className="font-mono text-sm text-gray-400 tracking-widest uppercase">— Winston Churchill</p>
            </div>
            <div className="space-y-8 text-lg lg:text-xl leading-loose text-gray-600 tracking-normal font-medium">
              <p>
                都市データや精密な3Dモデルは、画面の中では自在でも、触れられなければ実感になりません。紙の模型は、構造とスケールを「手触りのある理解」に変えてくれます。
              </p>
              <p>
                これまで複雑な形を紙に落とすには、展開図づくりと試作が必要でした。Paper-CADは幾何演算で切断線とのりしろを設計し、組み立てやすい展開図を自動生成します。
              </p>
              <p>
                データを「眺める」から「手元に置く」へ。創造の距離を縮めることが、私たちのミッションです。
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 02: Logic */}
      <section className="py-48 px-8 lg:px-16">
        <div className="max-w-[1200px] mx-auto">
	           <div className="flex justify-between items-end mb-24">
	               <div className="space-y-4 text-left">
	                <span className="font-mono text-[11px] font-bold tracking-[0.4em] text-gray-400 uppercase">02 TECHNOLOGY</span>
	                <h2 className="text-5xl font-black tracking-tighter">Unfoldを、設計する。</h2>
	              </div>
              <div className="hidden lg:block text-right">
                 <p className="font-mono text-[10px] text-gray-400 tracking-[0.2em] leading-relaxed">
                   ARCHITECTURE: OPEN CASCADE WASM<br/>
                   ALGORITHM: MINIMUM SPANNING TREE<br/>
                   RUNTIME: BROWSER NATIVE
                 </p>
              </div>
           </div>
           
	           <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-gray-100 border border-gray-100 rounded-2xl overflow-hidden shadow-2xl">
	              <div className="bg-white p-16 space-y-10 group">
	                 <div className="w-16 h-16 bg-gray-50 rounded-2xl flex items-center justify-center group-hover:bg-brand-orange group-hover:text-white transition-all duration-500">
	                    <Cpu className="w-8 h-8" />
	                 </div>
                 <h3 className="text-3xl font-black tracking-tighter">Indistinguishable from Magic.</h3>
                 <p className="text-lg text-gray-500 leading-relaxed font-medium">
                   「十分に発達した科学技術は、魔法と見分けがつかない。」<br/>
                   OpenCASCADEをWASM化し、ブラウザ上で産業グレードの幾何演算を実行。数万ポリゴンの都市データもローカルで解析し、展開図まで一気に生成します。
                 </p>
              </div>

	              <div className="bg-[#111] p-16 space-y-10 text-white relative overflow-hidden group">
	                 <div className="absolute inset-0 bg-brand-orange opacity-0 group-hover:opacity-10 transition-opacity duration-700"></div>
	                 <div className="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center group-hover:scale-110 transition-transform duration-500">
	                    <Layers className="w-8 h-8" />
	                 </div>
                 <h3 className="text-3xl font-black tracking-tighter">Graph Theory Optimization</h3>
                 <p className="text-lg text-gray-400 leading-relaxed font-medium">
                   3D形状の接続関係をグラフとして扱い、最小全域木（MST）で切断線とのりしろを最適化。組み立てやすさと造形の美しさを両立します。
                 </p>
              </div>
           </div>
        </div>
      </section>

      {/* Section 03: Recognition */}
      <section className="py-32 px-8 lg:px-16 bg-gray-50/50">
        <div className="max-w-[1200px] mx-auto">
          <div className="mb-10 flex flex-wrap items-center gap-6 text-left">
            <span className="font-mono text-[11px] font-bold tracking-[0.4em] text-gray-400 uppercase">03 RECORD</span>
            <h2 className="inline-flex items-center rounded-full border border-brand-orange/20 bg-brand-orange/10 px-5 py-2 text-sm font-black tracking-wide text-brand-orange md:text-base">
              受賞・採択実績
            </h2>
          </div>
          
          <div className="flex flex-wrap gap-3">
             {[
               { year: '2025', title: '未踏ジュニア 採択', desc: 'IPA（情報処理推進機構）独創的アイデア支援事業', highlight: true },
               { year: '2024', title: 'アプリ甲子園 優勝', desc: 'National Championship - Grand Prize', icon: <Trophy className="w-3 h-3" /> },
               { year: '2024', title: 'アプリ甲子園 技術賞', desc: 'Technical Award Excellence', icon: <Cpu className="w-3 h-3" /> },
               { year: '2024', title: 'アプリ甲子園 Cygames賞', desc: 'Corporate Special Recognition', icon: <Gamepad2 className="w-3 h-3" /> },
             ].map((award, i) => (
               <div
                 key={i}
                 title={`${award.title} — ${award.desc}`}
                 className={`group inline-flex items-center gap-3 rounded-full px-5 py-3 text-sm font-black tracking-tight transition-colors ${award.highlight ? 'bg-[#111] text-white shadow-lg border border-white/5' : 'bg-white text-[#111] border border-gray-200 hover:border-brand-orange/40 hover:bg-gray-50'}`}
               >
                 <span className={`font-mono text-[10px] font-bold tracking-[0.25em] uppercase ${award.highlight ? 'text-white/50' : 'text-gray-500'}`}>{award.year}</span>
                 {award.icon && <span className={`${award.highlight ? 'text-brand-orange' : 'text-gray-400'}`}>{award.icon}</span>}
                 <span>{award.title}</span>
                 {award.highlight && (
                   <span className="inline-flex items-center gap-2 rounded-full bg-brand-orange/15 px-3 py-1 text-[10px] font-bold tracking-[0.2em] uppercase text-brand-orange">
                     <Sparkles className="w-3 h-3 animate-pulse" /> Selected
                   </span>
                 )}
               </div>
             ))}
          </div>
        </div>
      </section>

      {/* Footer / Final CTA */}
      <footer className="bg-[#111] text-white pt-48 pb-0 px-8 lg:px-16 relative overflow-hidden">
         <div className="max-w-[1200px] mx-auto grid grid-cols-1 lg:grid-cols-2 gap-32 relative z-10">
            <div className="space-y-12">
               <h2 className="text-7xl lg:text-[9rem] font-black tracking-[-0.06em] leading-[0.8] uppercase opacity-20">
                 Unfold<br/>the<br/>World.
               </h2>
               <div className="space-y-8">
                 <a href="/app" className="inline-flex items-center gap-4 text-3xl font-black tracking-tighter hover:text-brand-orange transition-colors border-b-4 border-white hover:border-brand-orange pb-2 group">
                   Paper-CADを開く
                   <ChevronRight className="w-8 h-8 group-hover:translate-x-2 transition-transform" />
                 </a>
               </div>
            </div>

            <div className="flex flex-col justify-between">
               <div className="grid grid-cols-2 gap-24">
                  <div className="space-y-8 text-left">
                     <span className="block text-gray-600 font-mono text-[11px] font-bold tracking-[0.4em] uppercase">Connect</span>
                     <div className="flex flex-col gap-4 text-[15px] font-bold tracking-wide">
                        <a href="https://github.com/kodaimiyazaki/Paper-CAD" className="hover:text-brand-orange transition-colors inline-flex items-center gap-2">GitHub <Github className="w-3 h-3" /></a>
                        <a href="#" className="hover:text-brand-orange transition-colors">X / Twitter</a>
                        <a href="#" className="hover:text-brand-orange transition-colors">Documentation</a>
                     </div>
                  </div>
                  <div className="space-y-8 text-left">
                     <span className="block text-gray-600 font-mono text-[11px] font-bold tracking-[0.4em] uppercase">Project</span>
                     <div className="flex flex-col gap-4 text-[15px] font-bold tracking-wide">
                        <a href="#" className="hover:text-brand-orange transition-colors">About</a>
                        <a href="#" className="hover:text-brand-orange transition-colors">Contact</a>
                        <a href="#" className="hover:text-brand-orange transition-colors">Mitou Junior</a>
                     </div>
                  </div>
               </div>

               <div className="pt-32 border-t border-white/5 flex flex-col md:flex-row justify-between items-end md:items-center gap-8">
                  <div className="flex items-baseline gap-4">
                    <span className="font-black text-xl tracking-tighter uppercase">Paper—CAD</span>
                    <span className="font-mono text-[10px] text-gray-600 tracking-widest uppercase">© 2025 ALL RIGHTS RESERVED.</span>
                  </div>
                  <div className="text-right space-y-1">
                     <p className="font-mono text-[10px] text-gray-600 tracking-widest uppercase">Built by</p>
                     <p className="text-sm font-black tracking-tight">KODAI MIYAZAKI</p>
                  </div>
               </div>
            </div>
         </div>

         <div className="relative left-1/2 -translate-x-1/2 w-screen overflow-hidden pt-24">
            <p className="select-none whitespace-nowrap text-center font-black tracking-[-0.08em] leading-none text-brand-orange/10 text-[clamp(72px,18vw,260px)]">
              PaperCAD
            </p>
         </div>
         
         {/* Footer Brand Image - Strategic Placement */}
         <div className="absolute bottom-[-10%] right-[-5%] w-2/3 opacity-10 pointer-events-none mix-blend-lighten rotate-[-5deg]">
            <img src="/images/footer-brand.png" alt="" className="w-full h-auto" />
         </div>
      </footer>
    </div>
  );
}
