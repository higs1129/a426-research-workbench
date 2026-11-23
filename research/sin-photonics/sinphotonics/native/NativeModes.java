import com.comsol.model.*;
import com.comsol.model.util.*;
import java.io.*;
import java.util.*;
public class NativeModes {
 static Model m;
 static String root;
 static Properties cfg = new Properties();
 static double num(String key){return Double.parseDouble(cfg.getProperty(key));}
 static double first(String key){return Double.parseDouble(cfg.getProperty(key).split(" ")[0]);}
 static double[] weights(double[] edges,double[] steps){
  ArrayList<Double> values=new ArrayList<Double>();
  for(int k=0;k<steps.length;k++){int n=(int)Math.ceil((edges[k+1]-edges[k])/steps[k]);
   for(int i=0;i<n;i++)values.add((edges[k+1]-edges[k])/n*1e-6);}
  double[] out=new double[values.size()];for(int i=0;i<out.length;i++)out[i]=values.get(i);return out;
 }
 static void rect(String tag,double x,double y,double w,double h){
  GeomSequence g=m.component("c").geom("g");g.create(tag,"Rectangle");
  g.feature(tag).set("pos",new String[]{"Xoff/1[um]+("+x+")",Double.toString(y)});
  g.feature(tag).set("size",new double[]{w,h});g.feature(tag).set("selresult",true);
 }
  static void union(String tag,ArrayList<String> inputs){
    m.component("c").selection().create(tag,"Union");
    m.component("c").selection(tag).set("entitydim",2);
    m.component("c").selection(tag).set("input",inputs.toArray(new String[0]));
  }
  static void mat(String tag,String n,String sel){
    m.component("c").material().create(tag,"Common");
    if(sel==null)m.component("c").material(tag).selection().all();
    else m.component("c").material(tag).selection().named(sel);
    m.component("c").material(tag).propertyGroup().create("RefractiveIndex","Refractive_index");
    m.component("c").material(tag).propertyGroup("RefractiveIndex").set("n",new String[]{n});
    m.component("c").material(tag).propertyGroup("RefractiveIndex").set("ki",new String[]{"0"});
  }
  static void meshsize(String tag,String selection,String hmax,String hmin){
    m.component("c").mesh("mesh").create(tag,"Size");
    m.component("c").mesh("mesh").feature(tag).selection().geom("g",2);
    m.component("c").mesh("mesh").feature(tag).selection().named(selection);
    m.component("c").mesh("mesh").feature(tag).set("custom",true);
    m.component("c").mesh("mesh").feature(tag).set("hmax",hmax);
    m.component("c").mesh("mesh").feature(tag).set("hmin",hmin);
    m.component("c").mesh("mesh").feature(tag).set("hmaxactive",true);
    m.component("c").mesh("mesh").feature(tag).set("hminactive",true);
  }
  static java.util.zip.ZipOutputStream archive;
  static void array(String key,double[][] a) throws Exception {
    archive.putNextEntry(new java.util.zip.ZipEntry(key+".npy"));
    String header="{'descr': '<f8', 'fortran_order': False, 'shape': ("+a.length+", "+a[0].length+"), }";
    int pad=(64-(10+header.length()+1)%64)%64;
    for(int i=0;i<pad;i++)header+=" ";header+="\n";
    archive.write(new byte[]{(byte)147,'N','U','M','P','Y',1,0,(byte)(header.length()%256),(byte)(header.length()/256)});
    archive.write(header.getBytes("US-ASCII"));
    java.nio.ByteBuffer buffer=java.nio.ByteBuffer.allocate(8*a[0].length).order(java.nio.ByteOrder.LITTLE_ENDIAN);
    for(double[] row:a){buffer.clear();for(double v:row)buffer.putDouble(v);archive.write(buffer.array());}
    archive.closeEntry();archive.flush();
  }
  static double envnum(String key,double fallback){String value=System.getenv(key);return value==null?fallback:Double.parseDouble(value);}
  static double[] grid(double[] edges,double[] steps){
    ArrayList<Double> a=new ArrayList<Double>();
    for(int k=0;k<steps.length;k++){
      int n=(int)Math.ceil((edges[k+1]-edges[k])/steps[k]);
      for(int i=0;i<n;i++)a.add((edges[k]+(i+.5)*(edges[k+1]-edges[k])/n)*1e-6);
    }
    double[] r=new double[a.size()];for(int i=0;i<r.length;i++)r[i]=a.get(i);return r;
  }


 public static void main(String[]args)throws Exception{
  cfg.load(new InputStreamReader(new FileInputStream("run.properties"), "UTF-8"));
  root=cfg.getProperty("root");
  boolean bend=Boolean.parseBoolean(cfg.getProperty("bend"));String id=bend?"bend_modes":"straight_modes";
  double meshScale=num("mesh"),h=num("thickness_um"),wall=num("wall_deg"),lower=num("lower_oxide_um"),upper=num("upper_oxide_um");
  String out=root+"/models/"+id+".mph";
  if(new File(out).exists())throw new IOException("Existing model: "+out);
  m=ModelUtil.create("M");m.label(id+": native width / wavelength / radius sweep; parameterized bottom-width cross section");
  m.param().set("Wbottom",first("widths")+"[um]");m.param().set("Hcore",h+"[um]");m.param().set("wall",wall+"[deg]");
  m.param().set("Wcore","Wbottom-Hcore/tan(wall)");m.param().set("Rb",first("radii")+"[um]");
  m.param().set("Xoff",bend?"Rb":"0[um]");m.param().set("lambda0","1550[nm]");m.param().set("f0","c_const/lambda0");
  m.component().create("c",true);m.component("c").geom().create("g",2);GeomSequence g=m.component("c").geom("g");
  g.lengthUnit("um");if(bend)g.axisymmetric(true);
  double[] xs={-10,-8,8,10},ys={-7.5,-5.5,-lower-h/2,upper+h/2,4.5,6.5};
  ArrayList<String> pml=new ArrayList<String>(),si=new ArrayList<String>(),air=new ArrayList<String>(),inside=new ArrayList<String>();
  for(int i=0;i<3;i++)for(int j=0;j<5;j++){
   String t="r"+i+j;rect(t,xs[i],ys[j],xs[i+1]-xs[i],ys[j+1]-ys[j]);String sel="g_"+t+"_dom";
   if(i==0||i==2||j==0||j==4)pml.add(sel);else inside.add(sel);if(j<2)si.add(sel);if(j>=3)air.add(sel);
  }
  rect("near",-1.4,-.65,2.8,1.3);
  g.create("core","Polygon");g.feature("core").set("x",new String[]{"(Xoff-Wbottom/2)/1[um]","(Xoff+Wbottom/2)/1[um]","(Xoff+Wbottom/2-Hcore/tan(wall))/1[um]","(Xoff-Wbottom/2+Hcore/tan(wall))/1[um]"});
  g.feature("core").set("y",new String[]{"-Hcore/2/1[um]","-Hcore/2/1[um]","Hcore/2/1[um]","Hcore/2/1[um]"});g.feature("core").set("type","solid");g.feature("core").set("selresult",true);
  g.run();union("pmlDomains",pml);union("siDomains",si);union("airDomains",air);union("physical",inside);
  m.param().set("n_core_scan",cfg.getProperty("n_core"));
  m.param().set("n_oxide_scan",cfg.getProperty("n_oxide"));
  m.param().set("lower_oxide",lower+"[um]");m.param().set("upper_oxide",upper+"[um]");
  m.label(id+" | "+cfg.getProperty("material")+" | isolated cross-section modes");
  mat("oxide","n_oxide_scan",null);mat("silicon","3.48","siDomains");mat("air","1","airDomains");mat("core","n_core_scan","g_core_dom");
  m.component("c").physics().create("ewfd","ElectromagneticWavesFrequencyDomain","g");
  m.component("c").coordSystem().create("pml","PML");m.component("c").coordSystem("pml").selection().named("pmlDomains");
  m.component("c").coordSystem("pml").set("ScalingType",bend?"Cylindrical":"Cartesian");
  m.component("c").coordSystem("pml").set("stretchingType","rational");m.component("c").coordSystem("pml").set("wavelengthSourceType","userDefined");m.component("c").coordSystem("pml").set("typicalWavelength","lambda0");
  for(String t:new String[]{"intcore","intphys"}){m.component("c").cpl().create(t,"Integration");m.component("c").cpl(t).selection().named(t.equals("intcore")?"g_core_dom":"physical");if(bend)m.component("c").cpl(t).set("axisym",false);}
  m.param().set("mesh_scale",Double.toString(meshScale));m.component("c").mesh().create("mesh");
  m.component("c").mesh("mesh").feature("size").set("custom",true);m.component("c").mesh("mesh").feature("size").set("hmax",".35[um]*mesh_scale");m.component("c").mesh("mesh").feature("size").set("hmin",".008[um]");
  meshsize("nearSize","g_near_dom",".10[um]*mesh_scale",".008[um]");meshsize("coreSize","g_core_dom",".035[um]*mesh_scale",".008[um]");
  m.component("c").mesh("mesh").create("tri","FreeTri");m.component("c").mesh("mesh").feature("tri").selection().named("physical");m.component("c").mesh("mesh").create("mapped","Map");m.component("c").mesh("mesh").feature("mapped").selection().named("pmlDomains");
  String[] seeds=cfg.getProperty("seeds").split(","),channels=cfg.getProperty("channels").split(",");int count=(int)num("count");
  for(int k=0;k<seeds.length;k++){
   String st="st"+k;m.study().create(st);m.study(st).label(channels[k]+" native parameter sweep");
   m.study(st).create("param","Parametric");
   m.study(st).feature("param").set("pname",new String[]{"Wbottom","lambda0","Rb"});
   m.study(st).feature("param").set("plistarr",new String[]{cfg.getProperty("widths"),cfg.getProperty("wavelengths"),cfg.getProperty("radii")});
   m.study(st).feature("param").set("punit",new String[]{"um","nm","um"});m.study(st).feature("param").set("sweeptype","filled");
   m.study(st).feature("param").set("keepsol","all");m.study(st).feature("param").set("save","off");m.study(st).feature("param").set("paramselect","off");
   m.study(st).create("mode","ModeAnalysis");m.study(st).feature("mode").set("modeFreq","f0");m.study(st).feature("mode").set("transform","effective_mode_index");
   m.study(st).feature("mode").set("neigsactive",true);m.study(st).feature("mode").set("neigs",4);
   m.study(st).feature("mode").set("shiftactive",true);m.study(st).feature("mode").set("shift","("+seeds[k]+")"+(bend?"*Rb":""));
   m.study(st).setGenPlots(false);System.out.println("NATIVE_SWEEP_START "+id+" study="+st+" cases="+count);m.study(st).run();
   String[] datasets=m.result().dataset().tags();String data=datasets[datasets.length-1];
   System.out.println("NATIVE_SWEEP_SOLVED "+id+" dataset="+data);
   String ev="ev"+k;m.result().numerical().create(ev,"EvalGlobal");m.result().numerical(ev).set("data",data);
   m.result().numerical(ev).set("expr",new String[]{"real(c.ewfd.neff"+(bend?"/Rb":"")+")","imag(c.ewfd.neff"+(bend?"/Rb":"")+")","c.intcore(c.ewfd.normE^2)/c.intphys(c.ewfd.normE^2)",bend?"c.intcore(abs(c.ewfd.Er)^2)/c.intcore(abs(c.ewfd.Er)^2+abs(c.ewfd.Ez)^2)":"c.intcore(abs(c.ewfd.Ex)^2)/c.intcore(abs(c.ewfd.Ex)^2+abs(c.ewfd.Ey)^2)","n_core_scan","n_oxide_scan","Wbottom/1[um]","lambda0/1[nm]","Rb/1[um]"});
   String[] fields=bend?new String[]{"ewfd.Er","ewfd.Ez","ewfd.Ephi","ewfd.Hr","ewfd.Hz","ewfd.Hphi"}:new String[]{"ewfd.Ex","ewfd.Ey","ewfd.Ez","ewfd.Hx","ewfd.Hy","ewfd.Hz"};
   String[] expr=new String[12];for(int e=0;e<6;e++){expr[2*e]="real("+fields[e]+")";expr[2*e+1]="imag("+fields[e]+")";}
   for(int outer=1;outer<=count;outer++){
    double[][] info=m.result().numerical(ev).getReal(outer);double w=info[6][0],wl=info[7][0],r=info[8][0],off=bend?r:0;
    archive=new java.util.zip.ZipOutputStream(new BufferedOutputStream(new FileOutputStream(root+"/raw/"+id+"_s"+k+"_p"+outer+".npz")));
    array("info",info);
    double cot=1/Math.tan(Math.toRadians(wall)),mid=w-h*cot;
    double[][] coords=new double[2][101];for(int j=0;j<101;j++){coords[0][j]=off+(-.499+.998*j/100)*mid;coords[1][j]=0;}
    String ip="ip"+k;m.result().numerical().create(ip,"Interp");m.result().numerical(ip).set("data",data);m.result().numerical(ip).set("outersolnum",new int[]{outer});m.result().numerical(ip).set("coord",coords);m.result().numerical(ip).set("expr",Arrays.copyOf(expr,6));
    double[][][] vals=m.result().numerical(ip).getData();ArrayList<Integer> keep=new ArrayList<Integer>();
    for(int j=0;j<info[0].length;j++){
     double[][] f=new double[6][];for(int e=0;e<6;e++)f[e]=vals[e][j];array("line_"+j,f);int n=nodes(f,info[3][j]>.5?0:1);
     if(((channels[k].startsWith("TE") && info[3][j]>.8)||(channels[k].startsWith("TM") && info[3][j]<.2)) && info[2][j]>.015 && n==Integer.parseInt(channels[k].substring(2)) && Math.abs(info[1][j])<.03){keep.add(j);System.out.println("MODE "+id+" w="+w+" wl="+wl+" r="+r+" n="+n+" neff="+info[0][j]+" im="+info[1][j]+" core="+info[2][j]);}
    }
    if(keep.size()>0){
     double[] xe={-7.8,-3,-1,1,3,7.8},xsamp={.1,.035,.02,.035,.1};
     double[] ye={-5.5,-lower-h/2,-1-h/2,-h/2,h/2,1+h/2,upper+h/2,4.5},ysamp={.10,.08,.03,.01,.03,.08,.10};
     double[] x=grid(xe,xsamp),y=grid(ye,ysamp);
     array("wx",new double[][]{weights(xe,xsamp)});array("wy",new double[][]{weights(ye,ysamp)});
     array("cross_section",new double[][]{{h,wall,lower,upper}});
     array("x",new double[][]{x});array("y",new double[][]{y});double[][] full=new double[2][x.length*y.length];
     for(int iy=0;iy<y.length;iy++)for(int ix=0;ix<x.length;ix++){int j=iy*x.length+ix;full[0][j]=x[ix]*1e6+off;full[1][j]=y[iy]*1e6;}
     m.result().numerical(ip).set("coord",full);m.result().numerical(ip).set("expr",expr);vals=m.result().numerical(ip).getData();
     for(int j:keep){double[][] f=new double[12][];for(int e=0;e<12;e++)f[e]=vals[e][j];array("full_"+j,f);}
     double[] eta=new double[161],yy=new double[41];for(int j=0;j<161;j++)eta[j]=-.999+1.998*j/160;for(int j=0;j<41;j++)yy[j]=(-.4995*h+.999*h*j/40)*1e-6;
     array("eta",new double[][]{eta});array("core_y",new double[][]{yy});double[][] tc=new double[2][eta.length*yy.length];
     for(int iy=0;iy<yy.length;iy++)for(int ix=0;ix<eta.length;ix++){int j=iy*eta.length+ix;tc[0][j]=off+eta[ix]*(mid/2-yy[iy]*1e6*cot);tc[1][j]=yy[iy]*1e6;}
     m.result().numerical(ip).set("coord",tc);m.result().numerical(ip).set("expr",Arrays.copyOf(expr,6));vals=m.result().numerical(ip).getData();
     for(int j:keep){double[][] f=new double[6][];for(int e=0;e<6;e++)f[e]=vals[e][j];array("core_"+j,f);}
    }
    m.result().numerical().remove(ip);archive.close();System.out.println("EXPORTED "+id+" study="+k+" outer="+outer);
   }
  }
  String[] ds=m.result().dataset().tags();
  m.result().create("modefield","PlotGroup2D");m.result("modefield").label("Mode field | select dataset / outer parameter / eigenmode");
  m.result("modefield").set("data",ds[ds.length-1]);m.result("modefield").create("surf","Surface");
  m.result("modefield").feature("surf").set("expr","ewfd.normE");
  m.save(out);
  Model check=ModelUtil.loadCopy("Readback",out);
  int solved=0;for(String tag:check.sol().tags())if(!check.sol(tag).isEmpty())solved++;
  if(solved==0)throw new IOException("Readback has no solutions");
  System.out.println("READBACK_NONEMPTY_SOLVERS "+solved);
  ModelUtil.remove("Readback");System.out.println("COMPLETE "+id);
 }
  static int nodes(double[][] f,int component){
    double[] re=f[2*component],im=f[2*component+1];int imax=0;double amp=0;
    for(int j=0;j<101;j++){double v=Math.hypot(re[j],im[j]);if(v>amp){amp=v;imax=j;}}
    double ph=Math.atan2(im[imax],re[imax]);int n=0,sign=0;
    for(int j=0;j<101;j++){double v=re[j]*Math.cos(ph)+im[j]*Math.sin(ph);if(Math.abs(v)<.02*amp)continue;int next=v>0?1:-1;if(sign!=0&&next!=sign)n++;sign=next;}
    return n;
  }
}
