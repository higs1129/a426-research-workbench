import com.comsol.model.*;
import com.comsol.model.util.*;
import java.io.*;
import java.util.*;

/** Reopen saved MPH and compare every exported parameter/solution identity. */
public class VerifySweep {
 public static void main(String[] args)throws Exception {
  Properties p=new Properties();p.load(new InputStreamReader(new FileInputStream("run.properties"),"UTF-8"));
  File root=new File(p.getProperty("source"));
  PrintWriter out=new PrintWriter(new OutputStreamWriter(new FileOutputStream(p.getProperty("output")),"UTF-8"));
  out.println("family,model,study,dataset,outer,eigenmode,width_bottom_um,wavelength_nm,radius_um,neff_real,neff_imag");
  for(String family:new String[]{"ring","bus"}){
   BufferedReader in=new BufferedReader(new InputStreamReader(new FileInputStream(new File(root,family+"/native-map.csv")),"UTF-8"));
   in.readLine();String line;Model m=null;
   while((line=in.readLine())!=null){
    String[] a=line.split(",");
    if(m==null)m=ModelUtil.loadCopy("Verify",new File(root,family+"/models/"+a[0]).getAbsolutePath());
    String ev="ev"+a[1].substring(2);
    if(!m.result().numerical(ev).getString("data").equals(a[2]))throw new IOException("Dataset mismatch");
    int outer=Integer.parseInt(a[3]),j=Integer.parseInt(a[4])-1;
    double[][] v=m.result().numerical(ev).getReal(outer);
    for(int k=0;k<3;k++)if(Math.abs(v[6+k][j]-Double.parseDouble(a[5+k]))>1e-8)throw new IOException("Parameter identity mismatch: "+line);
    out.println(family+","+String.join(",",Arrays.copyOf(a,8))+","+v[0][j]+","+v[1][j]);out.flush();
   }
   in.close();ModelUtil.remove("Verify");
  }
  out.close();System.out.println("COMPLETE parameter/solution readback");
 }
}
