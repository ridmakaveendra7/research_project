--------------------------------------------------------------------------------
--                       FixFunctionByTable_Freq1_uid2
-- Evaluator for log(x+0.1)/log(2) on [0,1) for lsbIn=-3 (wIn=3), msbout=2, lsbOut=-3 (wOut=6). Out interval: [-3.32193; -0.0365259]. Output is signed

-- VHDL generated for Kintex7 @ 1MHz
-- This operator is part of the Infinite Virtual Library FloPoCoLib
-- All rights reserved 
-- Authors: Florent de Dinechin (2010-2018)
--------------------------------------------------------------------------------
-- combinatorial
-- Clock period (ns): 1000
-- Target frequency (MHz): 1
-- Input signals: X
-- Output signals: Y
--  approx. input signal timings: X: (c0, 0.000000ns)
--  approx. output signal timings: Y: (c0, 0.543000ns)

library ieee;
use ieee.std_logic_1164.all;
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;
library std;
use std.textio.all;
library work;

entity FixFunctionByTable_Freq1_uid2 is
    port (X : in  std_logic_vector(2 downto 0);
          Y : out  std_logic_vector(5 downto 0)   );
end entity;

architecture arch of FixFunctionByTable_Freq1_uid2 is
signal Y0 :  std_logic_vector(5 downto 0);
   -- timing of Y0: (c0, 0.543000ns)
signal Y1 :  std_logic_vector(5 downto 0);
   -- timing of Y1: (c0, 0.543000ns)
begin
   with X  select  Y0 <= 
      "100101" when "000",
      "101111" when "001",
      "110100" when "010",
      "110111" when "011",
      "111010" when "100",
      "111100" when "101",
      "111110" when "110",
      "000000" when "111",
      "------" when others;
   Y1 <= Y0; -- for the possible blockram register
   Y <= Y1;
end architecture;

