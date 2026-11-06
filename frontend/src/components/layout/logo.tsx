import React from 'react';

export default function Logo() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <svg 
        width="32" 
        height="32" 
        viewBox="0 0 48 48" 
        fill="none" 
        xmlns="http://www.w3.org/2000/svg"
      >
        <path 
          d="M14 20C15.6569 20 17 18.6569 17 17H31C31 18.6569 32.3431 20 34 20V28C32.3431 28 31 29.3431 31 31H17C17 29.3431 15.6569 28 14 28V20Z" 
          stroke="white" 
          strokeWidth="2" 
          strokeLinecap="round" 
          strokeLinejoin="round"
        />
        <path 
          d="M24 19V22M24 26V29" 
          stroke="white" 
          strokeWidth="2" 
          strokeLinecap="round"
        />
      </svg>
      <div style={{ 
        color: 'white', 
        fontFamily: "'Poppins', sans-serif",
        fontSize: '24px', 
        fontWeight: 700,
        letterSpacing: '2px'
      }}>
        TICKET-U
      </div>
    </div>
  );
}