//==============================================================================
//	
//	Copyright (c) 2002-
//	Authors:
//	* Dave Parker <david.parker@comlab.ox.ac.uk> (University of Oxford, formerly University of Birmingham)
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

package parser.visitor;

import java.util.Vector;

import parser.ast.*;
import prism.PrismLangException;

/**
 * Perform any required semantic checks. Optionally pass in parent ModulesFile
 * and PropertiesFile for some additional checks (or leave null);
 */
public class SemanticCheck extends ASTTraverse
{
	private ModulesFile modulesFile;
	private PropertiesFile propertiesFile;

	public SemanticCheck()
	{
		this(null, null);
	}

	public SemanticCheck(ModulesFile modulesFile)
	{
		this(modulesFile, null);
	}

	public SemanticCheck(ModulesFile modulesFile, PropertiesFile propertiesFile)
	{
		setModulesFile(modulesFile);
		setPropertiesFile(propertiesFile);
	}

	public void setModulesFile(ModulesFile modulesFile)
	{
		this.modulesFile = modulesFile;
	}

	public void setPropertiesFile(PropertiesFile propertiesFile)
	{
		this.propertiesFile = propertiesFile;
	}

	public void visitPost(ModulesFile e) throws PrismLangException
	{
		int i, j, n, n2;
		Module module;
		Vector<String> v;

		// Check for use of init...endinit _and_ var initial values
		if (e.getInitialStates() != null) {
			n = e.getNumGlobals();
			for (i = 0; i < n; i++) {
				if (e.getGlobal(i).isStartSpecified())
					throw new PrismLangException("Cannot use both \"init...endinit\" and initial values for variables",
							e.getGlobal(i).getStart());
			}
			n = e.getNumModules();
			for (i = 0; i < n; i++) {
				module = e.getModule(i);
				n2 = module.getNumDeclarations();
				for (j = 0; j < n2; j++) {
					if (module.getDeclaration(j).isStartSpecified())
						throw new PrismLangException(
								"Cannot use both \"init...endinit\" and initial values for variables", module
										.getDeclaration(j).getStart());
				}
			}
		}

		// Check system...endsystem construct (if present)
		// Each modules should appear exactly once
		if (e.getSystemDefn() != null) {
			e.getSystemDefn().getModules(v = new Vector<String>());
			if (v.size() != e.getNumModules()) {
				throw new PrismLangException("All modules must appear in the \"system\" construct exactly once", e
						.getSystemDefn());
			}
			n = e.getNumModules();
			for (i = 0; i < n; i++) {
				if (!(v.contains(e.getModuleName(i)))) {
					throw new PrismLangException("All modules must appear in the \"system\" construct exactly once", e
							.getSystemDefn());
				}
			}
		}
	}

	public void visitPost(LabelList e) throws PrismLangException
	{
		int i, n;
		String s;
		n = e.size();
		for (i = 0; i < n; i++) {
			s = e.getLabelName(i);
			if ("deadlock".equals(s))
				throw new PrismLangException("Cannot define a label called \"deadlock\" - this is a built-in label", e
						.getLabel(i));
			if ("init".equals(s))
				throw new PrismLangException("Cannot define a label called \"init\" - this is a built-in label", e
						.getLabel(i));
		}
	}

	public void visitPost(ConstantList e) throws PrismLangException
	{
		int i, n;
		n = e.size();
		for (i = 0; i < n; i++) {
			if (e.getConstant(i) != null && !e.getConstant(i).isConstant()) {
				throw new PrismLangException("Definition of constant \"" + e.getConstantName(i) + "\" is not constant",
						e.getConstant(i));
			}
		}
	}

	public void visitPost(Declaration e) throws PrismLangException
	{
		if (e.getLow() != null && !e.getLow().isConstant()) {
			throw new PrismLangException("Minimum value of variable \"" + e.getName() + "\" is not constant", e
					.getLow());
		}
		if (e.getHigh() != null && !e.getHigh().isConstant()) {
			throw new PrismLangException("Maximum value of variable \"" + e.getName() + "\" is not constant", e
					.getHigh());
		}
		if (e.getStart() != null && !e.getStart().isConstant()) {
			throw new PrismLangException("Initial value of variable \"" + e.getName() + "\" is not constant", e
					.getStart());
		}
	}

	public void visitPost(Update e) throws PrismLangException
	{
		int i, n;
		String s, var;
		Command c;
		Module m;
		ModulesFile mf;
		boolean isLocal, isGlobal;

		// Determine containing command/module/model
		// (mf should coincide with the stored modulesFile)
		c = e.getParent().getParent();
		m = c.getParent();
		mf = m.getParent();
		n = e.getNumElements();
		for (i = 0; i < n; i++) {
			// Check that the update is allowed to modify this variable
			var = e.getVar(i);
			isLocal = m.isLocalVariable(var);
			isGlobal = isLocal ? false : mf.isGlobalVariable(var);
			if (!isLocal && !isGlobal) {
				s = "Module \"" + m.getName() + "\" is not allowed to modify variable \"" + var + "\"";
				throw new PrismLangException(s, e.getVarIdent(i));
			}
			if (isGlobal && !c.getSynch().equals("")) {
				s = "Synchronous command cannot modify global variable";
				throw new PrismLangException(s, e.getVarIdent(i));
			}
		}
	}

	public void visitPost(SystemRename e) throws PrismLangException
	{
		int i, n;
		String s;
		Vector<String> v;

		// Check all actions are valid and ensure no duplicates
		// (only check "from": OK to introduce new actions and to map to same
		// action)
		v = new Vector<String>();
		n = e.getNumRenames();
		for (i = 0; i < n; i++) {
			s = e.getFrom(i);
			if (!modulesFile.isSynch(s)) {
				throw new PrismLangException("Invalid action \"" + s + "\" in \"system\" construct", e);
			}
			if (v.contains(s)) {
				throw new PrismLangException("Duplicated action \"" + s
						+ "\" in parallel composition in \"system\" construct", e);
			} else {
				v.addElement(s);
			}
		}
	}

	public void visitPost(SystemHide e) throws PrismLangException
	{
		int i, n;
		String s;
		Vector<String> v;

		// Check all actions are valid and ensure no duplicates
		v = new Vector<String>();
		n = e.getNumActions();
		for (i = 0; i < n; i++) {
			s = e.getAction(i);
			if (!modulesFile.isSynch(s)) {
				throw new PrismLangException("Invalid action \"" + s + "\" in \"system\" construct", e);
			}
			if (v.contains(s)) {
				throw new PrismLangException("Duplicated action \"" + s
						+ "\" in parallel composition in \"system\" construct", e);
			} else {
				v.addElement(s);
			}
		}
	}

	public void visitPost(SystemParallel e) throws PrismLangException
	{
		int i, n;
		String s;
		Vector<String> v;

		// Check all actions are valid and ensure no duplicates
		v = new Vector<String>();
		n = e.getNumActions();
		for (i = 0; i < n; i++) {
			s = e.getAction(i);
			if (!modulesFile.isSynch(s)) {
				throw new PrismLangException("Invalid action \"" + s + "\" in \"system\" construct", e);
			}
			if (v.contains(s)) {
				throw new PrismLangException("Duplicated action \"" + s
						+ "\" in parallel composition in \"system\" construct", e);
			} else {
				v.addElement(s);
			}
		}
	}

	public void visitPost(ExpressionTemporal e) throws PrismLangException
	{
		int op = e.getOperator();
		Expression operand1 = e.getOperand1();
		Expression operand2 = e.getOperand2();
		Expression lBound = e.getLowerBound();
		Expression uBound = e.getUpperBound();
		if (lBound != null && !lBound.isConstant()) {
			throw new PrismLangException("Lower bound in " + e.getOperatorSymbol() + " operator is not constant",
					lBound);
		}
		if (uBound != null && !uBound.isConstant()) {
			throw new PrismLangException("Upper bound in " + e.getOperatorSymbol() + " operator is not constant",
					uBound);
		}
		// Other checks (which parser should never allow to occur anyway)
		if (op == ExpressionTemporal.P_X
				&& (operand1 != null || operand2 == null || lBound != null || uBound != null)) {
			throw new PrismLangException("Cannot attach bounds to " + e.getOperatorSymbol() + " operator", e);
		}
		if (op == ExpressionTemporal.R_C
				&& (operand1 != null || operand2 != null || lBound != null || uBound == null)) {
			throw new PrismLangException("Badly formed " + e.getOperatorSymbol() + " operator", e);
		}
		if (op == ExpressionTemporal.R_I
				&& (operand1 != null || operand2 != null || lBound != null || uBound == null)) {
			throw new PrismLangException("Badly formed " + e.getOperatorSymbol() + " operator", e);
		}
		if (op == ExpressionTemporal.R_F
				&& (operand1 != null || operand2 == null || lBound != null || uBound != null)) {
			throw new PrismLangException("Badly formed " + e.getOperatorSymbol() + " operator", e);
		}
		if (op == ExpressionTemporal.R_S
				&& (operand1 != null || operand2 != null || lBound != null || uBound != null)) {
			throw new PrismLangException("Badly formed " + e.getOperatorSymbol() + " operator", e);
		}
	}
	
	public void visitPost(ExpressionFunc e) throws PrismLangException
	{
		// Check function name is valid
		if (e.getNameCode() == -1) {
			throw new PrismLangException("Unknown function \"" + e.getName() + "\"", e);
		}
		// Check num arguments
		if (e.getNumOperands() < e.getMinArity()) {
			throw new PrismLangException("Not enough arguments to \"" + e.getName() + "\" function", e);
		}
		if (e.getMaxArity() != -1 && e.getNumOperands() > e.getMaxArity()) {
			throw new PrismLangException("Too many " + e.getMaxArity() + "arguments to \"" + e.getName()
					+ "\" function", e);
		}
	}

	public void visitPost(ExpressionIdent e) throws PrismLangException
	{
		// By the time the expression is checked, this should
		// have been converted to an ExpressionVar/ExpressionConstant/...
		throw new PrismLangException("Undeclared identifier", e);
	}

	public void visitPost(ExpressionFormula e) throws PrismLangException
	{
		// This should have been expanded by now
		throw new PrismLangException("Unexpanded formula", e);
	}

	public void visitPost(ExpressionProb e) throws PrismLangException
	{
		if (e.getProb() != null && !e.getProb().isConstant()) {
			throw new PrismLangException("P operator probability bound is not constant", e.getProb());
		}
	}

	public void visitPost(ExpressionReward e) throws PrismLangException
	{
		if (e.getRewardStructIndex() != null) {
			if (e.getRewardStructIndex() instanceof Expression) {
				Expression rsi = (Expression) e.getRewardStructIndex();
				if (!(rsi.isConstant())) {
					throw new PrismLangException("R operator reward struct index is not constant", rsi);
				}
			}
			else if (e.getRewardStructIndex() instanceof String) {
				String s = (String) e.getRewardStructIndex();
				if (modulesFile != null && modulesFile.getRewardStructIndex(s) == -1) {
					throw new PrismLangException("R operator reward struct index \""+s+"\" does not exist", e);
				}
			}
		}
		if (e.getReward() != null && !e.getReward().isConstant()) {
			throw new PrismLangException("R operator reward bound is not constant", e.getReward());
		}
	}

	public void visitPost(ExpressionSS e) throws PrismLangException
	{
		if (e.getProb() != null && !e.getProb().isConstant()) {
			throw new PrismLangException("S operator probability bound is not constant", e.getProb());
		}
	}

	public void visitPost(ExpressionLabel e) throws PrismLangException
	{
		LabelList labelList;
		if (propertiesFile != null)
			labelList = propertiesFile.getCombinedLabelList();
		else if (modulesFile != null)
			labelList = modulesFile.getLabelList();
		else
			throw new PrismLangException("Undeclared label", e);
		String name = e.getName();
		// Allow special cases
		if ("deadlock".equals(name) || "init".equals(name))
			return;
		// Otherwise check list
		if (labelList == null || labelList.getLabelIndex(name) == -1) {
			throw new PrismLangException("Undeclared label", e);
		}
	}
}
