//==============================================================================
//	
//	Copyright (c) 2017-
//	Authors:
//	* Dave Parker <d.a.parker@cs.bham.ac.uk> (University of Birmingham)
//	
//------------------------------------------------------------------------------
//	
//	This file is part of PRISM.
//	
//	PRISM is free software; you can redistribute it and/or modify
//	it under the terms of the GNU General Public License as published by
//	the Free Software Foundation; either version 2 of the License, or
//	(at your option) any later version.
//	
//	PRISM is distributed in the hope that it will be useful,
//	but WITHOUT ANY WARRANTY; without even the implied warranty of
//	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//	GNU General Public License for more details.
//	
//	You should have received a copy of the GNU General Public License
//	along with PRISM; if not, write to the Free Software Foundation,
//	Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
//	
//==============================================================================

package demos;

import java.io.FileOutputStream;
import java.io.PrintStream;

import java.io.File;
import java.io.FileNotFoundException;
import java.util.ArrayList;
import java.util.List;

import parser.ast.*;
import prism.PrismLangException;
import prism.PrismUtils;
import parser.type.*;

import prism.ModelType;
import prism.Prism;
import prism.PrismDevNullLog;
import prism.PrismException;
import prism.PrismLog;
import prism.Result;
import prism.UndefinedConstants;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;

import Jama.Matrix;


/**
 * An example class demonstrating how to control PRISM programmatically, through
 * the functions exposed by the class prism.Prism.
 * 
 * This shows how to load a model from a file and model check some properties,
 * either from a file or specified as a string, and possibly involving
 * constants.
 * 
 * See the README for how to link this to PRISM.
 */
public class grid_world {
	public static int x_max = 0;
	public static int y_max = 0;
	public static int actions = 0;
	public static Matrix P_OPT;
	public static Matrix policy;
	public static Matrix unsafe;
	public static int TRANSITIONS = 0;
	public static int STATES = 0;
	public static ArrayList<String> dtmc; 
	public static void main(String[] args) throws IOException, InterruptedException, PrismLangException {
		new grid_world().run(args[0]);
	}

	static final public void ConstantDef(ConstantList constantList, ArrayList<String> lines) {
		String sLastLine = lines.get(0), sCurrentLine = lines.get(1);
		for (String line : lines) {
			if (lines.indexOf(line) % 2 == 1) {
				sCurrentLine = line;
				try {
					if (sLastLine.equals("x_max"))
						x_max = Integer.parseInt(sCurrentLine);
					else if (sLastLine.equals("y_max"))
						y_max = Integer.parseInt(sCurrentLine);
					else if (sLastLine.equals("actions"))
						actions = Integer.parseInt(sCurrentLine);
					constantList.addConstant(new ExpressionIdent(sLastLine),
							new ExpressionLiteral(TypeInt.getInstance(), Integer.parseInt(sCurrentLine)),
							TypeInt.getInstance());
				} catch (NumberFormatException e) {
					constantList.addConstant(new ExpressionIdent(sLastLine),
							new ExpressionLiteral(TypeDouble.getInstance(), Double.parseDouble(sCurrentLine)),
							TypeDouble.getInstance());
				}
			} else {
				sLastLine = line;
			}
		}
	}

	static final public void ParsePolicy(ArrayList<String> lines) {
		policy = new Matrix(new double[y_max * x_max + 2][y_max * x_max + 2]);
		for (int i = 0; i < lines.size(); i++) {
			String[] line = lines.get(i).split(" ");
			policy.set(Integer.parseInt(line[0]), Integer.parseInt(line[1]), (1.0 - unsafe.get(Integer.parseInt(line[0]), 0)) * Double.parseDouble(line[2]));
		}
		for (int i = 0; i <= y_max * x_max + 1; i++) {
			policy.set(i, y_max * x_max + 1 , unsafe.get(i, 0));
		}
	}
	
	static final public void ParseUnsafe(ArrayList<String> lines) {
		unsafe = new Matrix(new double[y_max * x_max + 2][1]);
		for (int i = 0; i < lines.size(); i++) {
			String[] line = lines.get(i).split(":");
			unsafe.set(Integer.parseInt(line[0])*x_max + Integer.parseInt(line[1]), 0, 1.0);
		}
		unsafe.set(y_max * x_max + 1, 0, 1.0); 
	}

	static final public void Normalize_Transitions(int i, double p_total) {
		if(p_total < 1.0) {
			Double p = policy.get(i, i);
			policy.set(i, i, p + 1.0 - p_total - 0.0001);
			System.out.println("Row " + Integer.toString(i) + " Operation Complete");
		}
		else if (p_total > 1.0) {
			for(int j = 0; j < policy.getColumnDimension(); j++) {
				Double p = policy.get(i, j);
				if(p > p_total - 1.0 + 0.0001) {
					policy.set(i, j, p - (p_total - 1.0 + 0.0001));
					p_total = p_total - (p_total - 1.0 + 0.0001);
					System.out.println("Row " + Integer.toString(i) + " Operation Complete");
					break;	
				}
				else {
					policy.set(i, j, 0.0);
					p_total = p_total - p;
				}
			}
		}	
	}
	
	static final public void Check_Transitions() {
		for(int i = 0; i< policy.getRowDimension(); i++) {
			Boolean recheck = true;
			while(recheck) {
				Double p_total = 0.0;
				for(int j = 0; j < policy.getColumnDimension(); j++) {
					p_total = p_total + policy.get(i, j); 
				}
				if(p_total != 1.0) {
					System.out.println("Row " + Integer.toString(i) + " prob sum is not 1.0 but " + Double.toString(p_total));
					Normalize_Transitions(i, p_total);
				}
				else
					recheck = false;
				
				recheck = false;
			}
		}
				
	}
	

	static final public Module Module(String name, ConstantList constantList, FormulaList formulaList) {
		Module m = new Module(name);
		m.setName(name);
		m.addDeclaration(new Declaration("x", new DeclarationInt(new ExpressionLiteral(TypeInt.getInstance(), 0),
				new ExpressionLiteral(TypeInt.getInstance(), x_max+1))));
		m.addDeclaration(new Declaration("y", new DeclarationInt(new ExpressionLiteral(TypeInt.getInstance(), 0),
				new ExpressionLiteral(TypeInt.getInstance(), y_max+1))));
		build_cmd(m);
		return m;
	}

	static final public void build_cmd(Module m) {
		dtmc = new ArrayList<String>();
		for (int i = 0; i < policy.getRowDimension(); i++) {
			double p_total = 0.0;
		    int y = (int)i/x_max;
		    int x = (int)i%x_max;
			Command c = new Command();
			Updates us = new Updates();
			Update u = new Update();
			c.setGuard(new ExpressionLiteral(TypeBool.getInstance(),  "((x= "+ x + ") & (y= " + y + ")) = true"));
			for (int j = 0; j < policy.getColumnDimension(); j++) {
				double p = policy.get(i, j);
				if(p > 0.0) {
					p_total += p;
					int y_ = (int)j/x_max;
				    int x_ = (int)j%x_max;
					u.addElement(new ExpressionIdent("x"), new ExpressionLiteral(TypeInt.getInstance(), Integer.toString(x_)));
					u.addElement(new ExpressionIdent("y"), new ExpressionLiteral(TypeInt.getInstance(), Integer.toString(y_)));
					us.addUpdate(new ExpressionLiteral(TypeDouble.getInstance(), Double.toString(p)), u);
					TRANSITIONS = TRANSITIONS + 1;
					dtmc.add(Integer.toString(i) + ' ' + Integer.toString(j) + ' ' + Double.toString(p * 0.99999));
					u = new Update();
				}
			}
			if(p_total > 0.0) {
				STATES = STATES + 1;
				c.setUpdates(us);
				m.addCommand(c);
			}
		} 
	}
	
	static final public void Write_DTMC() {
		dtmc.add(0, "STATES " + Integer.toString(STATES));
		dtmc.add(1, "TRANSITIONS " + Integer.toString(TRANSITIONS));
		dtmc.add(2, "INITIAL " + Integer.toString(policy.getColumnDimension()- 2));
		dtmc.add(3, "TARGET " + Integer.toString(policy.getColumnDimension() - 1));
	}
	
	static final public void run(String path) throws InterruptedException, FileNotFoundException {
		try {
			// Create a log for PRISM output (hidden or stdout)
			PrismLog mainLog = new PrismDevNullLog();
			// PrismLog mainLog = new PrismFileLog("stdout");

			// Initialise PRISM engine
			Prism prism = new Prism(mainLog);
			prism.initialise();

			ModulesFile mf = new ModulesFile();

			mf.setModelType(ModelType.DTMC);

			ArrayList<String> files = new ArrayList<String>();
			String STATE_SPACE = path + "/state_space";
			String OPT_POLICY = path + "/optimal_policy";
			String UNSAFE = path + "/unsafe";
			files.add(STATE_SPACE);
			files.add(UNSAFE);
			files.add(OPT_POLICY);
			ArrayList<String> lines = new ArrayList<String>();
			for (String file : files) {
				BufferedReader br = null;
				FileReader fr = null;
				try {
					fr = new FileReader(file);
					br = new BufferedReader(fr);
					String line;
					br = new BufferedReader(new FileReader(file));
					while ((line = br.readLine()) != null) {
						lines.add(line);
					}
					if (file.equals(STATE_SPACE)) {
						ConstantDef(mf.getConstantList(), lines);
						lines.clear();
					}
					if (file.equals(UNSAFE)) {
						ParseUnsafe(lines);
						lines.clear();
					}
					if (file.equals(OPT_POLICY)) {
						ParsePolicy(lines);
						lines.clear();
					}
				} catch (IOException e) {
					e.printStackTrace();
				}
			}

			//Check_Transitions();
			
			Module m_opt = Module("grid_world", mf.getConstantList(), mf.getFormulaList());
			mf.addModule(m_opt);
			Write_DTMC();
			//mf.setInitialStates(new ExpressionLiteral(TypeBool.getInstance(), "x = 0 & y = 0"));
			mf.setInitialStates(new ExpressionLiteral(TypeBool.getInstance(),
					"y = " + Integer.toString(y_max) + "& x = " + Integer.toString(0)));
			mf.tidyUp();
			//System.out.println(mf);
			prism.loadPRISMModel(mf);
			PrintStream ps_console = System.out;
			PrintStream ps_file = new PrintStream(new FileOutputStream(
					new File(path + "/grid_world.pm")));
			System.setOut(ps_file);
			System.out.println(mf);
			
			
			PrintStream dtmc_file = new PrintStream(new FileOutputStream(
					new File(path + "/grid_world.dtmc")));
			System.setOut(dtmc_file);
			for(String i:dtmc) {
				System.out.println(i);
			}
			
			System.setOut(ps_console);
			/**
			System.out.println(mf);
			PropertiesFile pf = prism.parsePropertiesFile(mf,
					new File(path + "/grid_world.pctl"));
			Result result = prism.modelCheck(pf, pf.getPropertyObject(0));
			System.out.println(result.getResult());
			**/

			System.exit(1);
		} catch (FileNotFoundException e) {
			System.out.println("Error: " + e.getMessage());
			System.exit(1);
		} catch (PrismException e) {
			System.out.println("Error: " + e.getMessage());
			System.exit(1);
		}

	}
}