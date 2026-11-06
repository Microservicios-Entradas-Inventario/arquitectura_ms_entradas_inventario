"use client";

import React from 'react';

export default function SearchButton() {
  const handleClick = () => {
    window.location.href = '/catalogo'; 
  };

  return (
    <button 
      onClick={handleClick}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "transparent",
        border: "1.5px solid #FFFFFF",
        borderRadius: "6px",
        padding: "4px 8px",
        color: "#FFFFFF",
        cursor: "pointer",
        gap: "2px",
        transition: "background 0.2s ease, opacity 0.2s ease"
      }}
    >
      <svg 
        width="20" 
        height="20" 
        viewBox="0 0 24 24" 
        fill="none" 
        stroke="currentColor" 
        strokeWidth="2" 
        strokeLinecap="round" 
        strokeLinejoin="round"
      >
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
      </svg>
      <span style={{ 
        fontSize: "10px", 
        fontWeight: 700, 
        fontFamily: "'Inter', sans-serif",
        letterSpacing: "0.5px" 
      }}>
        BUSCAR
      </span>
    </button>
  );
}