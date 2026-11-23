import com.comsol.model.*;
import com.comsol.model.util.*;
import java.io.*;
import java.util.*;

/** Read-only native loadCopy inspection. Does not save or modify input models. */
public class InspectModels {
 public static void main(String[]args)throws Exception {
  Properties p=new Properties();p.load(new InputStreamReader(new FileInputStream("run.properties"),"UTF-8"));
  File folder=new File(p.getProperty("models"));
  PrintWriter out=new PrintWriter(new OutputStreamWriter(new FileOutputStream(p.getProperty("output")),"UTF-8"));
  try {
   out.println("model,studies,solvers,nonempty_solvers,components");
   for(File file:folder.listFiles()){
    if(!file.getName().endsWith(".mph"))continue;
    Model m=ModelUtil.loadCopy("Inspect",file.getAbsolutePath());int nonempty=0;
    for(String tag:m.sol().tags())if(!m.sol(tag).isEmpty())nonempty++;
    out.println(file.getName()+","+m.study().tags().length+","+m.sol().tags().length+","+nonempty+","+m.component().tags().length);
    ModelUtil.remove("Inspect");out.flush();
   }
  } finally {out.close();}
  System.out.println("COMPLETE model inspection");
 }
}
