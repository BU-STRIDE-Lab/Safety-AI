//==============================================================================
//	
//	Copyright (c) 2002-
//	Authors:
//	* Andrew Hinton <ug60axh@cs.bham.ac.uk> (University of Birmingham)
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

package settings;

/**
 *
 * @author  Andrew Hinton
 */
public class DoubleRangeConstraint implements SettingConstraint
{
    private double lower, upper;
    private boolean inclusiveLower, inclusiveUpper;
    
    /** Creates a new instance of DoubleRangeConstraint */
    public DoubleRangeConstraint(String parseThis)
    {
    }
    
    public DoubleRangeConstraint(double lower, double upper, boolean inclusiveLower, boolean inclusiveUpper)
    {
        this.lower = lower;
        this.upper = upper;
        this.inclusiveLower = inclusiveLower;
        this.inclusiveUpper = inclusiveUpper;
    }
    
    public void checkValue(Object value) throws SettingException
    {
        
    }
    
}