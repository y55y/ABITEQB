// Temporary script to analyze quiz data
const fs = require('fs');

try {
    const content = fs.readFileSync('index.html', 'utf8');

    // Extract quizData array
    const quizDataMatch = content.match(/const quizData = \[([\s\S]*?)\];/);

    if (quizDataMatch) {
        const quizDataContent = quizDataMatch[1];

        // Count question objects by looking for question_number entries
        const questionMatches = quizDataContent.match(/"question_number":\s*\d+/g);

        if (questionMatches) {
            console.log('Total question objects found:', questionMatches.length);

            // Extract question numbers
            const questionNumbers = questionMatches.map(match => {
                const numMatch = match.match(/\d+/);
                return numMatch ? parseInt(numMatch[0]) : null;
            }).filter(num => num !== null).sort((a, b) => a - b);

            console.log('Question numbers range:', Math.min(...questionNumbers), 'to', Math.max(...questionNumbers));

            // Check for gaps
            const gaps = [];
            for (let i = 0; i < questionNumbers.length - 1; i++) {
                if (questionNumbers[i + 1] !== questionNumbers[i] + 1) {
                    gaps.push(`${questionNumbers[i]} -> ${questionNumbers[i + 1]}`);
                }
            }

            if (gaps.length > 0) {
                console.log('Gaps found:', gaps);
            } else {
                console.log('No gaps found in question numbering');
            }

            console.log('Expected array length should be:', questionMatches.length);
        } else {
            console.log('No question_number entries found');
        }
    } else {
        console.log('Could not find quizData array');
    }
} catch (error) {
    console.error('Error:', error.message);
}
