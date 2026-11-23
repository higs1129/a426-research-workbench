import com.comsol.model.*;
import com.comsol.model.util.*;
import java.io.*;
import java.util.*;

/** Export compact clear-solution templates without modifying source models. */
public class ExportTemplates {
 public static void main(String[]args)throws Exception {
  Properties p=new Properties();p.load(new InputStreamReader(new FileInputStream("run.properties"),"UTF-8"));
  for(String kind:new String[]{"bend","straight"}){
   String target=p.getProperty("output")+"/"+kind+"-cleared-template.mph";
   if(new File(target).exists())throw new IOException("Existing output "+target);
   Model m=ModelUtil.loadCopy("Template",p.getProperty(kind));
   for(String tag:m.sol().tags())m.sol(tag).clearSolutionData();
   for(String c:m.component().tags())for(String mesh:m.component(c).mesh().tags())m.component(c).mesh(mesh).clearMesh();
   m.label(kind+" | clear-solution template | rebuild mesh and study to solve");m.save(target);
   ModelUtil.remove("Template");Model check=ModelUtil.loadCopy("Check",target);
   for(String tag:check.sol().tags())if(!check.sol(tag).isEmpty())throw new IOException("Unexpected native solution");
   ModelUtil.remove("Check");
  }
  System.out.println("COMPLETE compact templates");
 }
}
