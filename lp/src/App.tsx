import { motion, useScroll, useTransform } from 'framer-motion';
import { 
  Box, 
  Layers, 
  Cpu, 
  Download, 
  Github, 
  ArrowRight,
  Globe,
  Hammer,
  Quote,
  Trophy,
  Gamepad2,
  Sparkles,
  ChevronRight
} from 'lucide-react';

// Smart, smooth easing - Apple style
const easeOutExpo = [0.16, 1, 0.3, 1];

const fadeInUp = {
  initial: { opacity: 0, y: 30 },
  animate: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 1.0, ease: easeOutExpo }
  }
};

const staggerContainer = {
  animate: {
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1
    }
  }
};

const floatAnimation = {
  animate: {
    y: [0, -15, 0],
    rotate: [0, 2, -2, 0],
    transition: {
      duration: 8,
      repeat: Infinity,
      ease: "easeInOut"
    }
  }
};

export default function App() {
  const { scrollYProgress } = useScroll();
  const y = useTransform(scrollYProgress, [0, 1], [0, -80]);

  return (
    <div className="min-h-screen bg-white text-slate-900 selection:bg-brand-500 selection:text-white overflow-x-hidden antialiased">
      
      {/* Navbar - Glassmorphism */}
      <nav className="fixed w-full z-50 top-0 left-0 border-b border-white/10 bg-white/70 backdrop-blur-xl transition-all duration-300">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3 font-bold text-xl tracking-tight">
            <motion.div 
              whileHover={{ rotate: 180 }}
              transition={{ duration: 0.6, ease: easeOutExpo }}
              className="p-2 bg-slate-900 rounded-lg text-white"
            >
              <Box className="w-5 h-5" />
            </motion.div>
            <span className="font-sans font-bold tracking-tight">Paper-CAD</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="https://github.com/kodaimiyazaki/Paper-CAD" target="_blank" rel="noreferrer" className="text-slate-500 hover:text-slate-900 transition-colors hidden sm:block">
              <Github className="w-5 h-5" />
            </a>
            <a href="/app" className="group px-6 py-2.5 bg-slate-900 text-white text-sm font-bold rounded-full hover:bg-brand-600 transition-all hover:shadow-lg hover:shadow-brand-500/30 flex items-center gap-2">
              アプリを起動
              <ChevronRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </a>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-40 pb-24 lg:pt-60 lg:pb-40 px-6 overflow-hidden">
        <div className="max-w-7xl mx-auto relative z-10">
          <motion.div 
            initial="initial"
            animate="animate"
            variants={staggerContainer}
            className="flex flex-col items-center text-center"
          >
             <motion.div variants={fadeInUp} className="mb-8 inline-flex items-center gap-3 px-5 py-2 rounded-full bg-slate-50 text-slate-600 text-xs font-bold border border-slate-200 tracking-wider uppercase">
              <Sparkles className="w-3.5 h-3.5 text-brand-500" />
              <span>Open Source Public Beta</span>
            </motion.div>

            <motion.div variants={fadeInUp} className="max-w-5xl mx-auto mb-12">
              <h1 className="text-5xl lg:text-8xl font-serif font-medium text-slate-900 leading-[1.2] tracking-wide">
                画面の中の建築を、<br/>
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-slate-900 via-slate-700 to-slate-900">
                  掌の上へ。
                </span>
              </h1>
            </motion.div>
            
            <motion.div variants={fadeInUp} className="max-w-2xl mx-auto mb-12">
               <div className="flex items-start justify-center gap-4 text-slate-500 mb-8">
                  <Quote className="w-8 h-8 opacity-20 -mt-2" />
                  <div className="text-left">
                    <p className="text-lg font-serif italic leading-relaxed text-slate-700">
                      「まず我々が建物を形作り、<br/>その後、建物が我々を形作る。」
                    </p>
                    <p className="text-xs font-bold tracking-widest mt-3 uppercase opacity-60">— Winston Churchill</p>
                  </div>
               </div>

               <p className="text-lg lg:text-xl text-slate-600 leading-loose font-light tracking-wide">
                 Paper-CADは、CityGMLやSTEPデータを<br className="hidden sm:block"/>
                 物理的な<strong className="text-slate-900 font-medium border-b border-brand-300">ペーパーモデル</strong>へと昇華させる、<br className="hidden sm:block"/>
                 建築家とメイカーのための空間変換エンジンです。
               </p>
            </motion.div>
            
            <motion.div variants={fadeInUp} className="flex flex-col sm:flex-row items-center justify-center gap-5">
              <motion.a 
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                href="#magic" 
                className="px-10 py-5 bg-slate-900 text-white rounded-full font-bold hover:bg-brand-600 transition-all flex items-center gap-3 shadow-2xl shadow-slate-900/10 tracking-wide text-sm"
              >
                テクノロジーの深淵を見る <ArrowRight className="w-4 h-4" />
              </motion.a>
              <motion.a 
                whileHover={{ scale: 1.02, backgroundColor: '#f8fafc' }}
                whileTap={{ scale: 0.98 }}
                href="https://github.com/kodaimiyazaki/Paper-CAD" 
                target="_blank" 
                rel="noreferrer" 
                className="px-10 py-5 bg-white text-slate-700 border border-slate-200 rounded-full font-bold transition-all hover:border-slate-300 tracking-wide text-sm"
              >
                GitHub
              </motion.a>
            </motion.div>

            {/* Awards Section - Minimal & Clean */}
            <motion.div variants={fadeInUp} className="pt-24 w-full max-w-6xl mx-auto">
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
                
                {/* App Koshien - Major Feature */}
                <div className="lg:col-span-7 bg-gradient-to-br from-slate-50 to-white border border-slate-100 rounded-[2rem] p-10 relative overflow-hidden group hover:shadow-lg transition-shadow duration-500">
                  <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
                    <Trophy className="w-32 h-32" />
                  </div>
                  <div className="relative z-10 flex flex-col h-full justify-between items-start text-left">
                    <div className="space-y-4">
                      <span className="inline-block px-3 py-1 bg-amber-100 text-amber-800 text-[10px] font-black tracking-widest uppercase rounded">Triple Crown</span>
                      <div>
                        <h4 className="text-3xl font-bold text-slate-900 tracking-tight mb-2">アプリ甲子園 2024</h4>
                        <p className="text-slate-500 font-medium">日本最大級のU-22開発者コンテスト</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-3 mt-8">
                       <div className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-full text-xs font-bold shadow-lg shadow-slate-900/20">
                         <Trophy className="w-3 h-3 text-amber-400" /> 優勝 (Grand Prize)
                       </div>
                       <div className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-full text-xs font-bold">
                         <Cpu className="w-3 h-3 text-brand-500" /> 技術賞
                       </div>
                       <div className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-full text-xs font-bold">
                         <Gamepad2 className="w-3 h-3 text-slate-900" /> Cygames賞
                       </div>
                    </div>
                  </div>
                </div>

                {/* Mitou Junior - Secondary Feature */}
                <div className="lg:col-span-5 bg-slate-900 text-white rounded-[2rem] p-10 relative overflow-hidden group hover:shadow-xl hover:shadow-slate-900/20 transition-all duration-500">
                   <div className="absolute -bottom-10 -right-10 w-48 h-48 bg-brand-500 rounded-full blur-[80px] opacity-20 group-hover:opacity-40 transition-opacity"></div>
                   <div className="relative z-10 flex flex-col h-full justify-between items-start text-left">
                     <div className="space-y-4">
                        <span className="inline-block px-3 py-1 bg-white/10 text-brand-200 text-[10px] font-black tracking-widest uppercase rounded">Innovation</span>
                        <div>
                          <h4 className="text-2xl font-bold tracking-tight mb-2">未踏ジュニア</h4>
                          <p className="text-slate-400 text-sm leading-relaxed">IPA（情報処理推進機構）<br/>2025年度 採択プロジェクト</p>
                        </div>
                     </div>
                     <div className="mt-8 flex items-center gap-3">
                        <div className="w-2 h-2 bg-brand-400 rounded-full animate-pulse"></div>
                        <span className="text-xs font-bold tracking-wider text-brand-100">FUNDED & SUPPORTED</span>
                     </div>
                   </div>
                </div>

              </div>
            </motion.div>
          </motion.div>
        </div>
        
        {/* Background Gradients */}
        <motion.div style={{ y }} className="absolute top-0 right-0 w-[800px] h-[800px] bg-gradient-to-b from-brand-50/50 to-transparent rounded-full blur-3xl -z-10 opacity-60" />
      </section>

      {/* The "Magic" Section - Dark Mode */}
      <section id="magic" className="py-40 bg-[#0B0F19] text-white relative overflow-hidden">
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent"></div>
        
        <div className="max-w-7xl mx-auto px-6 relative z-10">
          <div className="grid lg:grid-cols-2 gap-24 items-center">
            <motion.div 
               initial={{ opacity: 0, x: -40 }}
               whileInView={{ opacity: 1, x: 0 }}
               viewport={{ once: true, margin: "-100px" }}
               transition={{ duration: 1, ease: easeOutExpo }}
               className="space-y-12"
            >
              <div>
                <span className="text-brand-400 font-mono text-xs tracking-[0.3em] uppercase mb-4 block">Core Technology</span>
                <h2 className="text-4xl lg:text-5xl font-serif font-medium leading-tight mb-8">
                  <span className="text-slate-500 opacity-50 block text-2xl mb-2 font-sans font-light">Arthur C. Clarke said,</span>
                  「十分に発達した科学技術は、<br/>魔法と見分けがつかない。」
                </h2>
                <p className="text-lg text-slate-400 leading-loose font-light tracking-wide">
                  一見すると、それは単なる「折り紙」です。<br/>
                  しかしその背後には、産業グレードの演算処理が存在します。<br/>
                  独自のアルゴリズムが<strong className="text-white font-medium mx-1">CityGML</strong>の複雑な位相幾何を解析し、
                  展開図という「解」を瞬時に導き出します。
                </p>
              </div>

              <div className="space-y-6">
                 <div className="group flex items-start gap-6 p-6 rounded-2xl bg-white/5 border border-white/5 hover:bg-white/10 hover:border-white/10 transition-colors cursor-default">
                    <div className="p-3 bg-brand-500/10 rounded-xl text-brand-400 group-hover:text-brand-300 transition-colors">
                      <Cpu className="w-6 h-6" />
                    </div>
                    <div>
                      <h4 className="text-lg font-bold mb-2">OpenCASCADE Core</h4>
                      <p className="text-slate-400 text-sm leading-relaxed">
                        ブラウザ上で動作する、産業用CADカーネル(WASM)。<br/>
                        数万ポリゴンの都市データも、ローカル環境で高速に処理します。
                      </p>
                    </div>
                 </div>
                 
                 <div className="group flex items-start gap-6 p-6 rounded-2xl bg-white/5 border border-white/5 hover:bg-white/10 hover:border-white/10 transition-colors cursor-default">
                    <div className="p-3 bg-brand-500/10 rounded-xl text-brand-400 group-hover:text-brand-300 transition-colors">
                      <Layers className="w-6 h-6" />
                    </div>
                    <div>
                      <h4 className="text-lg font-bold mb-2">Graph Theory Unfolding</h4>
                      <p className="text-slate-400 text-sm leading-relaxed">
                        形状をグラフ構造として捉え、最小全域木（MST）アルゴリズムを用いて
                        「最も美しく、組み立てやすい」展開経路を探索します。
                      </p>
                    </div>
                 </div>
              </div>
            </motion.div>

            <div className="relative">
              <motion.div 
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 1.2, ease: easeOutExpo }}
                className="relative z-10 bg-gradient-to-b from-slate-800 to-slate-900 rounded-[2.5rem] p-2 border border-white/10 shadow-2xl"
              >
                 <div className="aspect-square rounded-[2rem] overflow-hidden bg-[#0F131F] relative flex items-center justify-center">
                    <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-soft-light"></div>
                    
                    {/* Visual Animation */}
                    <motion.div variants={floatAnimation} animate="animate" className="relative w-64 h-64 perspective-1000">
                       <motion.div 
                         animate={{ rotateY: [0, 360] }}
                         transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                         className="w-full h-full transform-style-3d"
                       >
                         <div className="absolute inset-0 border border-brand-500/30 bg-brand-500/5 rounded-xl backdrop-blur-sm"></div>
                         <div className="absolute inset-4 border border-white/10 rounded-xl transform translate-z-10"></div>
                         <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 bg-brand-500 rounded-full blur-[80px] opacity-40"></div>
                       </motion.div>
                    </motion.div>
                    
                    <div className="absolute bottom-10 left-10 right-10 flex justify-between items-end">
                      <div className="font-mono text-[10px] text-brand-500/70 tracking-widest">
                        GEOMETRY_PROCESSING<br/>STATUS: ACTIVE
                      </div>
                      <div className="text-right">
                         <div className="text-4xl font-bold tracking-tighter text-white">3D<span className="text-slate-600 mx-2">→</span>2D</div>
                      </div>
                    </div>
                 </div>
              </motion.div>
              
              {/* Glow effects */}
              <div className="absolute -inset-10 bg-brand-500/20 blur-[100px] -z-10 rounded-full opacity-50"></div>
            </div>
          </div>
        </div>
      </section>

      {/* Features / Use Cases */}
      <section className="py-40 px-6 bg-slate-50 relative">
        <div className="max-w-7xl mx-auto">
          <div className="text-center max-w-3xl mx-auto mb-24 space-y-6">
            <h2 className="text-4xl lg:text-5xl font-serif font-bold text-slate-900 tracking-wide">
              都市を、<br/>デスクトップサイズへ。
            </h2>
            <p className="text-lg text-slate-600 font-light leading-loose tracking-wide">
              都市開発のシミュレーションから、個人のホビーユースまで。<br/>
              Paper-CADは、データの規模を問わず、直感的な実体化をサポートします。
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
             {[
               {
                 icon: <Globe className="w-8 h-8" />,
                 title: "CityGML & PLATEAU",
                 desc: "国土交通省PLATEAUなどのオープンデータを直接インポート。巨大な都市モデルも、A4サイズに分割して出力可能です。"
               },
               {
                 icon: <Hammer className="w-8 h-8" />,
                 title: "Precision Crafting",
                 desc: "「山折り」「谷折り」の自動判別はもちろん、のりしろの角度や干渉回避まで計算。組み立てやすさを第一に設計されています。"
               },
               {
                 icon: <Download className="w-8 h-8" />,
                 title: "Universal Export",
                 desc: "SVG、DXF、PDFに対応。レーザーカッターでの加工や、プロッターでの出力に最適化されたパスデータを生成します。"
               }
             ].map((item, i) => (
               <motion.div 
                 key={i}
                 initial={{ opacity: 0, y: 40 }}
                 whileInView={{ opacity: 1, y: 0 }}
                 viewport={{ once: true, margin: "-50px" }}
                 transition={{ delay: i * 0.15, duration: 0.8, ease: easeOutExpo }}
                 className="bg-white p-10 rounded-[2rem] shadow-sm border border-slate-100 hover:shadow-xl hover:shadow-slate-200/50 transition-all group cursor-default"
               >
                 <div className="w-16 h-16 bg-brand-50 rounded-2xl flex items-center justify-center text-brand-600 mb-8 group-hover:rotate-6 transition-transform duration-500">
                   {item.icon}
                 </div>
                 <h3 className="text-xl font-bold text-slate-900 mb-4 tracking-tight">{item.title}</h3>
                 <p className="text-slate-600 leading-loose text-sm font-light">
                   {item.desc}
                 </p>
               </motion.div>
             ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-40 px-6 text-center relative overflow-hidden bg-white">
        <div className="max-w-4xl mx-auto space-y-12 relative z-10">
          <motion.div
             initial={{ opacity: 0, scale: 0.95 }}
             whileInView={{ opacity: 1, scale: 1 }}
             viewport={{ once: true }}
             transition={{ duration: 0.8, ease: easeOutExpo }}
          >
            <h2 className="text-5xl lg:text-7xl font-serif font-bold tracking-tight text-slate-900 mb-8">
              想像力を、実体化せよ。
            </h2>
            <p className="text-slate-500 text-lg font-light tracking-widest uppercase">
              Start folding your world today.
            </p>
          </motion.div>
          
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2, duration: 0.8, ease: easeOutExpo }}
            className="flex flex-col sm:flex-row items-center justify-center gap-6"
          >
            <a href="/app" className="group relative px-12 py-6 bg-slate-900 text-white text-lg rounded-full font-bold overflow-hidden shadow-2xl hover:shadow-brand-500/50 transition-all duration-300">
              <span className="relative z-10 flex items-center gap-2">
                Paper-CADを起動 <ChevronRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </span>
              <div className="absolute inset-0 bg-brand-600 transform scale-x-0 group-hover:scale-x-100 transition-transform origin-left duration-300 ease-out"></div>
            </a>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#050505] text-white pt-32 pb-12 px-6 overflow-hidden relative">
        <div className="max-w-7xl mx-auto relative z-10 flex flex-col md:flex-row justify-between items-start gap-16 mb-32">
          <div className="space-y-6 max-w-sm">
            <div className="flex items-center gap-3 font-bold text-2xl tracking-tight">
              <Box className="w-8 h-8 text-white" />
              <span>Paper-CAD</span>
            </div>
            <p className="text-slate-500 text-sm leading-loose">
              デジタルとフィジカルの境界を溶かす。<br/>
              未踏ジュニア2025採択プロジェクトとして開発中の、<br/>
              次世代ペーパーエンジニアリングツール。
            </p>
          </div>
          
          <div className="flex gap-20 text-sm text-slate-500">
            <div className="space-y-6 flex flex-col">
              <span className="font-bold text-white tracking-widest text-xs uppercase">Project</span>
              <a href="https://github.com/kodaimiyazaki/Paper-CAD" className="hover:text-white transition-colors">GitHub</a>
              <a href="#" className="hover:text-white transition-colors">Documentation</a>
              <a href="#" className="hover:text-white transition-colors">Mitou Junior</a>
            </div>
            <div className="space-y-6 flex flex-col">
              <span className="font-bold text-white tracking-widest text-xs uppercase">Legal</span>
              <a href="#" className="hover:text-white transition-colors">Privacy</a>
              <a href="#" className="hover:text-white transition-colors">Terms</a>
            </div>
          </div>
        </div>

        {/* MASSIVE BACKGROUND IMAGE */}
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[1920px] pointer-events-none select-none opacity-20 mix-blend-screen">
           <img 
             src="/images/footer-brand.png" 
             alt="PaperCAD Brand" 
             className="w-full h-auto object-cover mask-image-gradient"
           />
        </div>
        
        <div className="max-w-7xl mx-auto border-t border-white/5 pt-8 text-slate-600 text-xs flex justify-between items-center relative z-10">
          <div>© 2025 Paper-CAD Project. All rights reserved.</div>
          <div className="font-mono">TOKYO, JAPAN</div>
        </div>
      </footer>
    </div>
  );
}

